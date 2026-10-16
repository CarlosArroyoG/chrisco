"""Mantenimiento periódico de los equipos y alertas por correo al personal."""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.clock import today
from app.core.config import get_settings
from app.core.errors import Conflict, InvalidInput, NotFound
from app.models.equipo import Equipo, EquipoStatus
from app.models.gasto import GastoCategoria
from app.models.mantenimiento import MantenimientoPlan, MantenimientoRegistro
from app.models.user import Role, User
from app.schemas.gasto import GastoIn
from app.schemas.mantenimiento import (
    AtencionItem,
    Estado,
    PlanIn,
    PlanOut,
    RealizadoIn,
    RegistroOut,
)
from app.services import gastos, notifications
from app.services.mailer import Mailer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Situacion:
    estado: Estado
    faltan_horas: Decimal | None
    faltan_dias: int | None


def situacion(plan: MantenimientoPlan, horometro: Decimal, hoy: date) -> Situacion:
    """Qué tan cerca está el servicio. Puro: no toca la base de datos."""
    settings = get_settings()
    faltan_horas = (
        plan.ultimo_horometro + plan.cada_horas - horometro if plan.cada_horas is not None else None
    )
    faltan_dias = (
        (plan.ultima_fecha + timedelta(days=plan.cada_dias) - hoy).days
        if plan.cada_dias is not None
        else None
    )
    if (faltan_horas is not None and faltan_horas <= 0) or (
        faltan_dias is not None and faltan_dias <= 0
    ):
        estado: Estado = "vencido"
    elif (faltan_horas is not None and faltan_horas <= settings.mantenimiento_aviso_horas) or (
        faltan_dias is not None and faltan_dias <= settings.mantenimiento_aviso_dias
    ):
        estado = "proximo"
    else:
        estado = "ok"
    return Situacion(estado, faltan_horas, faltan_dias)


def plan_out(plan: MantenimientoPlan) -> PlanOut:
    s = situacion(plan, plan.equipo.horometro, today())
    return PlanOut(
        id=plan.id,
        equipo_id=plan.equipo_id,
        nombre=plan.nombre,
        cada_horas=plan.cada_horas,
        cada_dias=plan.cada_dias,
        ultimo_horometro=plan.ultimo_horometro,
        ultima_fecha=plan.ultima_fecha,
        activo=plan.activo,
        estado=s.estado,
        faltan_horas=s.faltan_horas,
        faltan_dias=s.faltan_dias,
    )


def attention_item(plan: MantenimientoPlan) -> AtencionItem:
    return AtencionItem(
        **plan_out(plan).model_dump(),
        equipo_codigo=plan.equipo.codigo,
        equipo_nombre=plan.equipo.nombre,
        horometro_actual=plan.equipo.horometro,
    )


def get_plan(db: Session, plan_id: uuid.UUID) -> MantenimientoPlan:
    plan = db.get(MantenimientoPlan, plan_id)
    if plan is None:
        raise NotFound("Plan de mantenimiento no encontrado")
    return plan


def list_for_equipo(db: Session, equipo_id: uuid.UUID) -> list[MantenimientoPlan]:
    return list(
        db.scalars(
            select(MantenimientoPlan)
            .where(MantenimientoPlan.equipo_id == equipo_id)
            .order_by(MantenimientoPlan.nombre)
        )
    )


def create_plan(db: Session, equipo: Equipo, data: PlanIn) -> MantenimientoPlan:
    """Da de alta el plan contando desde hoy y desde el horómetro actual del equipo."""
    if any(p.nombre.lower() == data.nombre.lower() for p in list_for_equipo(db, equipo.id)):
        raise Conflict("Ese equipo ya tiene un plan con ese nombre")
    plan = MantenimientoPlan(
        equipo_id=equipo.id,
        nombre=data.nombre,
        cada_horas=data.cada_horas,
        cada_dias=data.cada_dias,
        activo=data.activo,
        ultimo_horometro=equipo.horometro,
        ultima_fecha=today(),
    )
    db.add(plan)
    db.commit()
    return plan


def update_plan(db: Session, plan: MantenimientoPlan, data: PlanIn) -> MantenimientoPlan:
    others = [p for p in list_for_equipo(db, plan.equipo_id) if p.id != plan.id]
    if any(p.nombre.lower() == data.nombre.lower() for p in others):
        raise Conflict("Ese equipo ya tiene un plan con ese nombre")
    plan.nombre = data.nombre
    plan.cada_horas = data.cada_horas
    plan.cada_dias = data.cada_dias
    plan.activo = data.activo
    plan.alerta_enviada = None  # otro intervalo, otra situación: que vuelva a avisar si hace falta
    db.commit()
    return plan


def delete_plan(db: Session, plan: MantenimientoPlan) -> None:
    db.delete(plan)
    db.commit()


def register_done(
    db: Session, plan: MantenimientoPlan, staff: User, data: RealizadoIn
) -> MantenimientoRegistro:
    """El servicio se hizo: el plan vuelve a contar desde esa fecha y ese horómetro."""
    fecha = data.fecha or today()
    if fecha > today():
        raise InvalidInput("La fecha del servicio no puede ser futura")
    horometro = data.horometro if data.horometro is not None else plan.equipo.horometro
    registro = MantenimientoRegistro(
        fecha=fecha, horometro=horometro, notas=data.notas, registrado_por_id=staff.id
    )
    plan.registros.append(registro)
    if data.costo is not None:
        gastos.create(
            db,
            staff,
            GastoIn(
                fecha=fecha,
                categoria=GastoCategoria.MANTENIMIENTO,
                concepto=f"{plan.nombre} — {plan.equipo.codigo}",
                monto=data.costo,
                equipo_id=plan.equipo_id,
            ),
            commit=False,
        )
    plan.ultima_fecha = fecha
    plan.ultimo_horometro = horometro
    plan.alerta_enviada = None
    db.commit()
    return registro


def registro_out(registro: MantenimientoRegistro) -> RegistroOut:
    return RegistroOut(
        id=registro.id,
        fecha=registro.fecha,
        horometro=registro.horometro,
        notas=registro.notas,
        registrado_por_nombre=registro.registrado_por.full_name,
        created_at=registro.created_at,
    )


def _active_plans() -> Select[MantenimientoPlan]:
    return (
        select(MantenimientoPlan)
        .join(Equipo, MantenimientoPlan.equipo_id == Equipo.id)
        .where(MantenimientoPlan.activo.is_(True), Equipo.status != EquipoStatus.BAJA)
    )


def attention(db: Session, *, only_due: bool = False) -> list[AtencionItem]:
    """Planes activos de equipos que no están dados de baja, los más urgentes primero."""
    plans = db.scalars(_active_plans().order_by(Equipo.codigo, MantenimientoPlan.nombre))
    order = {"vencido": 0, "proximo": 1, "ok": 2}
    items = [attention_item(p) for p in plans]
    if only_due:
        items = [i for i in items if i.estado != "ok"]
    return sorted(items, key=lambda i: order[i.estado])


def send_alerts(db: Session, mailer: Mailer) -> int:
    """Avisa por correo a los administradores de los servicios próximos o vencidos.

    Cada plan avisa una vez por situación («próximo» y, después, «vencido»); se vuelve a armar
    cuando se registra el servicio. Se manda un solo correo por administrador con todo lo
    pendiente. Devuelve cuántos planes se avisaron.
    """
    pending = [(plan, attention_item(plan)) for plan in db.scalars(_active_plans())]
    # Si el servicio volvió a estar en orden (p. ej. se corrigió el intervalo), se rearma el aviso.
    for plan, item in pending:
        if item.estado == "ok":
            plan.alerta_enviada = None
    news = [(p, i) for p, i in pending if i.estado != "ok" and p.alerta_enviada != i.estado]
    if not news:
        db.commit()
        return 0
    admins = list(db.scalars(select(User).where(User.role == Role.ADMIN, User.is_active.is_(True))))
    if not admins:
        logger.warning("Hay mantenimientos por avisar pero no hay administradores activos")
        db.commit()
        return 0
    items = sorted((i for _, i in news), key=lambda i: (i.estado != "vencido", i.equipo_codigo))
    for admin in admins:
        mailer.send(notifications.maintenance_alert_mail(admin, items))
    for plan, item in news:
        plan.alerta_enviada = item.estado
    db.commit()
    return len(news)

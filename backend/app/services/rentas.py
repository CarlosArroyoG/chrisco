"""Solicitudes de renta de los clientes (fase 5). Las fases siguientes las llevan hasta el cobro."""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import Conflict, NotFound
from app.models.bloqueo import Bloqueo, BloqueoEstado
from app.models.cotizacion import Cotizacion, CotizacionEstado
from app.models.empresa import Empresa
from app.models.equipo import Equipo
from app.models.renta import Renta, RentaEstado, renta_folio_seq
from app.models.user import Role, User
from app.schemas.renta import PreviewOut, RentaOut, Requisito, SolicitudIn, WhatsappOut
from app.services import disponibilidad, equipos, requisitos, whatsapp

# Estados en los que una renta todavía depende de una reserva provisional que puede vencer.
_PROVISIONAL = (RentaEstado.SOLICITADA, RentaEstado.APARTADA)
_CANCELABLE = (RentaEstado.SOLICITADA, RentaEstado.COTIZADA, RentaEstado.APARTADA)
_STAFF = (Role.ADMIN, Role.VENTAS)
# Lo único de una renta que ve un operador: lo que entrega, lo que está en obra y lo que regresó.
OPERADOR_STATES = (RentaEstado.CONFIRMADA, RentaEstado.EN_RENTA, RentaEstado.DEVUELTA)


def expire_stale(db: Session) -> int:
    """Vence las reservas provisionales caducadas y, con ellas, las solicitudes que dependían de
    ellas (pasan a `vencida`). Devuelve cuántas reservas venció.

    Es seguro llamarla cuantas veces se quiera. No hace commit: lo decide quien la llama.
    """
    holds = disponibilidad.expire_holds(db)
    expired = select(Bloqueo.id).where(Bloqueo.estado == BloqueoEstado.EXPIRADO)
    db.execute(
        update(Renta)
        .where(Renta.estado.in_(_PROVISIONAL), Renta.bloqueo_id.in_(expired))
        .values(estado=RentaEstado.VENCIDA)
    )
    # Una cotización que pasó su vigencia sin respuesta vence; y una solicitud cotizada que se
    # quedó sin cotización viva vence con ella.
    db.execute(
        update(Cotizacion)
        .where(Cotizacion.estado == CotizacionEstado.VIGENTE, Cotizacion.valida_hasta <= func.now())
        .values(estado=CotizacionEstado.VENCIDA)
    )
    alive = select(Cotizacion.renta_id).where(
        Cotizacion.estado.in_((CotizacionEstado.VIGENTE, CotizacionEstado.ACEPTADA))
    )
    db.execute(
        update(Renta)
        .where(Renta.estado == RentaEstado.COTIZADA, Renta.id.not_in(alive))
        .values(estado=RentaEstado.VENCIDA)
    )
    return holds


def preview(db: Session, data: SolicitudIn) -> PreviewOut:
    """Qué se le va a pedir al cliente y si el equipo está libre, sin reservar nada."""
    equipo = equipos.get_active_equipo(db, data.equipo_id)
    return PreviewOut(
        disponible=disponibilidad.is_free(db, equipo, data.desde, data.hasta),
        requisitos=requisitos.compute(equipo, data.operador_modo, data.transporte),
    )


def _next_folio(db: Session) -> str:
    year = datetime.now(ZoneInfo(get_settings().timezone)).year
    return f"CHR-{year}-{db.scalar(select(renta_folio_seq.next_value())):05d}"


def create_request(db: Session, user: User, empresa: Empresa, data: SolicitudIn) -> Renta:
    """Reserva el equipo 20 min y registra la solicitud, todo en una sola transacción."""
    # Se bloquea la fila de la empresa: dos solicitudes simultáneas no pueden pasar del límite.
    db.execute(select(Empresa.id).where(Empresa.id == empresa.id).with_for_update())
    expire_stale(db)
    limit = get_settings().max_active_requests_per_company
    open_requests = db.scalar(
        select(func.count()).where(
            Renta.empresa_id == empresa.id, Renta.estado == RentaEstado.SOLICITADA
        )
    )
    if (open_requests or 0) >= limit:
        raise Conflict(
            f"Tu empresa ya tiene {limit} solicitudes abiertas. Espera a que ventas responda "
            "o cancela alguna."
        )

    equipo = equipos.get_active_equipo(db, data.equipo_id)
    items = requisitos.compute(equipo, data.operador_modo, data.transporte)
    bloqueo = disponibilidad.place_hold(db, equipo, data.desde, data.hasta, user, commit=False)
    renta = Renta(
        folio=_next_folio(db),
        empresa_id=empresa.id,
        solicitante_id=user.id,
        equipo_id=equipo.id,
        bloqueo_id=bloqueo.id,
        desde=data.desde,
        hasta=data.hasta,
        destino=data.destino,
        operador_modo=data.operador_modo,
        transporte=data.transporte,
        notas=data.notas,
        requisitos=[i.model_dump(mode="json") for i in items],
    )
    db.add(renta)
    db.commit()
    return renta


def get_for_user(db: Session, user: User, renta_id: uuid.UUID) -> Renta:
    """La renta, si el usuario es del personal o de la empresa dueña. Si no, «no existe»."""
    expire_stale(db)
    db.commit()
    renta = db.get(Renta, renta_id)
    visible = renta is not None and (
        user.role in _STAFF
        or (user.role == Role.OPERADOR and renta.estado in OPERADOR_STATES)
        or (user.role == Role.CLIENTE and renta.empresa_id == user.empresa_id)
    )
    if not visible:
        raise NotFound("Renta no encontrada")
    assert renta is not None
    return renta


def list_for(
    db: Session,
    user: User,
    *,
    estado: RentaEstado | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Renta], int]:
    expire_stale(db)
    db.commit()
    query = (
        select(Renta)
        .join(Empresa, Renta.empresa_id == Empresa.id)
        .join(Equipo, Renta.equipo_id == Equipo.id)
    )
    if user.role == Role.CLIENTE:
        query = query.where(Renta.empresa_id == user.empresa_id)
    if user.role == Role.OPERADOR:
        query = query.where(Renta.estado.in_(OPERADOR_STATES))
    if estado:
        query = query.where(Renta.estado == estado)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                Renta.folio.ilike(like),
                Empresa.razon_social.ilike(like),
                Equipo.nombre.ilike(like),
                Equipo.codigo.ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.options(
            selectinload(Renta.empresa),
            selectinload(Renta.equipo),
            selectinload(Renta.solicitante),
            selectinload(Renta.bloqueo),
        )
        .order_by(Renta.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(items), total


def cancel(db: Session, renta: Renta) -> Renta:
    if renta.estado not in _CANCELABLE:
        raise Conflict("Esta renta ya no se puede cancelar")
    renta.estado = RentaEstado.CANCELADA
    renta.motivo_cierre = "Cancelada a solicitud del cliente o del personal"
    if renta.bloqueo is not None and renta.bloqueo.estado == BloqueoEstado.ACTIVO:
        renta.bloqueo.estado = BloqueoEstado.LIBERADO  # el equipo queda libre al instante
    db.commit()
    return renta


# Estados en los que el cliente todavía tiene algo que hacer o esperar con un equipo.
OPEN_STATES = (
    RentaEstado.SOLICITADA,
    RentaEstado.COTIZADA,
    RentaEstado.APARTADA,
    RentaEstado.CONFIRMADA,
    RentaEstado.EN_RENTA,
)


def open_by_equipo(
    db: Session, empresa_id: uuid.UUID, equipo_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Renta]:
    """La renta abierta más reciente de la empresa para cada equipo (si la tiene)."""
    expire_stale(db)
    db.commit()
    rows = db.scalars(
        select(Renta)
        .where(
            Renta.empresa_id == empresa_id,
            Renta.equipo_id.in_(equipo_ids),
            Renta.estado.in_(OPEN_STATES),
        )
        .order_by(Renta.created_at)
    )
    return {renta.equipo_id: renta for renta in rows}  # la más reciente pisa a las anteriores


def to_out(renta: Renta) -> RentaOut:
    provisional = renta.estado in _PROVISIONAL and renta.bloqueo is not None
    return RentaOut(
        id=renta.id,
        folio=renta.folio,
        estado=renta.estado,
        empresa_id=renta.empresa_id,
        empresa_razon_social=renta.empresa.razon_social,
        solicitante_nombre=renta.solicitante.full_name,
        equipo_id=renta.equipo_id,
        equipo_codigo=renta.equipo.codigo,
        equipo_nombre=renta.equipo.nombre,
        equipo_foto_id=renta.equipo.fotos[0].id if renta.equipo.fotos else None,
        total=next(
            (
                c.total
                for c in renta.cotizaciones
                if c.estado in (CotizacionEstado.VIGENTE, CotizacionEstado.ACEPTADA)
            ),
            None,
        ),
        desde=renta.desde,
        hasta=renta.hasta,
        destino=renta.destino,
        operador_modo=renta.operador_modo,
        transporte=renta.transporte,
        notas=renta.notas,
        requisitos=[Requisito.model_validate(r) for r in renta.requisitos],
        vence_en=renta.bloqueo.vence_en if provisional and renta.bloqueo else None,
        motivo_cierre=renta.motivo_cierre,
        created_at=renta.created_at,
    )


def whatsapp_for(renta: Renta) -> WhatsappOut:
    message = whatsapp.build_message(renta)
    return WhatsappOut(mensaje=message, url=whatsapp.build_url(message))

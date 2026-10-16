"""Gastos del negocio: se registran a mano o los genera un servicio de mantenimiento con costo."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.clock import today
from app.core.errors import InvalidInput, NotFound
from app.models.equipo import Equipo
from app.models.gasto import Gasto, GastoCategoria
from app.models.user import User
from app.schemas.gasto import GastoIn, GastoOut, GastosOut


def month_bounds(month: str) -> tuple[date, date]:
    """`2026-10` → (1 de octubre, 1 de noviembre)."""
    try:
        year, number = (int(part) for part in month.split("-"))
        first = date(year, number, 1)
    except ValueError:
        raise InvalidInput("El mes debe tener el formato AAAA-MM") from None
    nxt = date(year + number // 12, number % 12 + 1, 1)
    return first, nxt


def create(
    db: Session,
    staff: User,
    data: GastoIn,
    *,
    commit: bool = True,
) -> Gasto:
    if data.fecha > today():
        raise InvalidInput("La fecha del gasto no puede ser futura")
    if data.equipo_id is not None and db.get(Equipo, data.equipo_id) is None:
        raise NotFound("Equipo no encontrado")
    gasto = Gasto(
        fecha=data.fecha,
        categoria=data.categoria,
        concepto=data.concepto,
        monto=data.monto,
        equipo_id=data.equipo_id,
        registrado_por_id=staff.id,
    )
    db.add(gasto)
    if commit:
        db.commit()
    return gasto


def delete(db: Session, gasto_id: uuid.UUID) -> None:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None:
        raise NotFound("Gasto no encontrado")
    db.delete(gasto)
    db.commit()


def _filtered(month: str | None, categoria: GastoCategoria | None) -> Select[Gasto]:
    query = select(Gasto)
    if month:
        first, nxt = month_bounds(month)
        query = query.where(Gasto.fecha >= first, Gasto.fecha < nxt)
    if categoria:
        query = query.where(Gasto.categoria == categoria)
    return query


def to_out(gasto: Gasto) -> GastoOut:
    return GastoOut(
        id=gasto.id,
        fecha=gasto.fecha,
        categoria=gasto.categoria,
        concepto=gasto.concepto,
        monto=gasto.monto,
        equipo_codigo=gasto.equipo.codigo if gasto.equipo else None,
        equipo_nombre=gasto.equipo.nombre if gasto.equipo else None,
        registrado_por_nombre=gasto.registrado_por.full_name,
        created_at=gasto.created_at,
    )


def listing(
    db: Session,
    *,
    month: str | None = None,
    categoria: GastoCategoria | None = None,
    limit: int = 25,
    offset: int = 0,
) -> GastosOut:
    query = _filtered(month, categoria)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    suma = db.scalar(select(func.coalesce(func.sum(query.subquery().c.monto), 0))) or Decimal(0)
    rows = db.scalars(
        query.order_by(Gasto.fecha.desc(), Gasto.created_at.desc()).limit(limit).offset(offset)
    )
    return GastosOut(items=[to_out(g) for g in rows], total=total, suma=Decimal(suma))

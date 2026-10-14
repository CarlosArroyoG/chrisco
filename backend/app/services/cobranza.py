"""Cobranza: cuánto se cotizó, cuánto se ha pagado y cuánto falta por renta."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.cotizacion import Cotizacion, CotizacionEstado
from app.models.cumplimiento import Pago, RevisionEstado
from app.models.empresa import Empresa
from app.models.equipo import Equipo
from app.models.renta import Renta, RentaEstado
from app.schemas.cumplimiento import CobranzaItem, CobranzaOut, CobranzaResumen

# Rentas que ya tienen una cotización aceptada y, por tanto, algo que cobrar.
_BILLABLE = (
    RentaEstado.APARTADA,
    RentaEstado.CONFIRMADA,
    RentaEstado.EN_RENTA,
    RentaEstado.DEVUELTA,
    RentaEstado.CERRADA,
)


def _base(
    estado: RentaEstado | None, q: str | None, only_balance: bool
) -> Select[uuid.UUID, str, str, str, RentaEstado, Decimal, Any]:
    """Una fila por renta cobrable: total cotizado y total confirmado."""
    paid = (
        select(Pago.renta_id, func.coalesce(func.sum(Pago.monto), 0).label("pagado"))
        .where(Pago.estado == RevisionEstado.APROBADO)
        .group_by(Pago.renta_id)
        .subquery()
    )
    pagado = func.coalesce(paid.c.pagado, 0)
    query = (
        select(
            Renta.id,
            Renta.folio,
            Empresa.razon_social,
            Equipo.nombre,
            Renta.estado,
            Cotizacion.total,
            pagado.label("pagado"),
        )
        .join(Cotizacion, Cotizacion.renta_id == Renta.id)
        .join(Empresa, Renta.empresa_id == Empresa.id)
        .join(Equipo, Renta.equipo_id == Equipo.id)
        .outerjoin(paid, paid.c.renta_id == Renta.id)
        .where(Cotizacion.estado == CotizacionEstado.ACEPTADA, Renta.estado.in_(_BILLABLE))
    )
    if estado:
        query = query.where(Renta.estado == estado)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                Renta.folio.ilike(like), Empresa.razon_social.ilike(like), Equipo.nombre.ilike(like)
            )
        )
    if only_balance:
        query = query.where(Cotizacion.total > pagado)
    return query


def summary(
    db: Session, *, estado: RentaEstado | None, q: str | None, only_balance: bool
) -> CobranzaResumen:
    rows = _base(estado, q, only_balance).subquery()
    total, pagado = db.execute(
        select(func.coalesce(func.sum(rows.c.total), 0), func.coalesce(func.sum(rows.c.pagado), 0))
    ).one()
    pending = db.scalar(
        select(func.count()).select_from(Pago).where(Pago.estado == RevisionEstado.PENDIENTE)
    )
    return CobranzaResumen(
        total_cotizado=Decimal(total),
        total_pagado=Decimal(pagado),
        saldo=Decimal(total) - Decimal(pagado),
        pagos_por_confirmar=pending or 0,
    )


def listing(
    db: Session,
    *,
    estado: RentaEstado | None = None,
    q: str | None = None,
    only_balance: bool = False,
    limit: int = 25,
    offset: int = 0,
) -> CobranzaOut:
    query = _base(estado, q, only_balance)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(query.order_by(Renta.created_at.desc()).limit(limit).offset(offset))
    items = [
        CobranzaItem(
            renta_id=renta_id,
            folio=folio,
            empresa=empresa,
            equipo=equipo,
            estado=state,
            total=total_cotizado,
            pagado=Decimal(pagado),
            saldo=total_cotizado - Decimal(pagado),
        )
        for renta_id, folio, empresa, equipo, state, total_cotizado, pagado in rows
    ]
    return CobranzaOut(
        items=items,
        total=total,
        resumen=summary(db, estado=estado, q=q, only_balance=only_balance),
    )

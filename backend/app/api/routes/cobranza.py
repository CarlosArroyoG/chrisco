"""Cobranza para los dueños: cuánto se cotizó, se ha cobrado y falta por cobrar."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession, StaffUser
from app.models.renta import RentaEstado
from app.schemas.cumplimiento import CobranzaOut
from app.services import cobranza

router = APIRouter(prefix="/admin/cobranza", tags=["cobranza"])


@router.get("", response_model=CobranzaOut)
def get_cobranza(
    _: StaffUser,
    db: DbSession,
    estado: RentaEstado | None = None,
    q: str | None = None,
    solo_con_saldo: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CobranzaOut:
    return cobranza.listing(
        db, estado=estado, q=q, only_balance=solo_con_saldo, limit=limit, offset=offset
    )

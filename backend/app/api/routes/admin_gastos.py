"""Gastos del negocio (ver: admin y ventas; registrar y borrar: solo admin)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, DbSession, StaffUser
from app.models.gasto import GastoCategoria
from app.schemas.gasto import GastoIn, GastoOut, GastosOut
from app.services import gastos

router = APIRouter(prefix="/admin/gastos", tags=["gastos"])


@router.get("", response_model=GastosOut)
def list_gastos(
    _: StaffUser,
    db: DbSession,
    mes: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
    categoria: GastoCategoria | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> GastosOut:
    return gastos.listing(db, month=mes, categoria=categoria, limit=limit, offset=offset)


@router.post("", response_model=GastoOut, status_code=status.HTTP_201_CREATED)
def create_gasto(admin: AdminUser, body: GastoIn, db: DbSession) -> GastoOut:
    return gastos.to_out(gastos.create(db, admin, body))


@router.delete("/{gasto_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gasto(_: AdminUser, gasto_id: uuid.UUID, db: DbSession) -> None:
    gastos.delete(db, gasto_id)

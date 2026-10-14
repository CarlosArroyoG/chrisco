"""Salida y regreso del equipo con horómetro y foto del tablero."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CatalogUser, DbSession, StaffUser, StorageDep
from app.api.forms import MovimientoForm
from app.core.errors import NotFound
from app.schemas.movimiento import MovimientoOut, MovimientosOut
from app.services import movimientos, rentas
from app.services.storage import read_limited

router = APIRouter(prefix="/rentas/{renta_id}/movimientos", tags=["movimientos"])


@router.get("", response_model=MovimientosOut)
def list_movimientos(user: CatalogUser, renta_id: uuid.UUID, db: DbSession) -> MovimientosOut:
    return movimientos.listing(rentas.get_for_user(db, user, renta_id))


@router.post("", response_model=MovimientoOut, status_code=status.HTTP_201_CREATED)
def register_movimiento(
    staff: StaffUser,
    renta_id: uuid.UUID,
    datos: MovimientoForm,
    foto: Annotated[UploadFile, File(description="Foto del horómetro")],
    db: DbSession,
    storage: StorageDep,
) -> MovimientoOut:
    renta = rentas.get_for_user(db, staff, renta_id)
    movimiento = movimientos.register(db, storage, renta, staff, datos, read_limited(foto))
    return movimientos.to_out(movimiento)


@router.get("/{movimiento_id}/foto", response_class=FileResponse)
def download_foto(
    user: CatalogUser,
    renta_id: uuid.UUID,
    movimiento_id: uuid.UUID,
    db: DbSession,
    storage: StorageDep,
) -> FileResponse:
    renta = rentas.get_for_user(db, user, renta_id)
    movimiento = next((m for m in renta.movimientos if m.id == movimiento_id), None)
    if movimiento is None:
        raise NotFound("Movimiento no encontrado")
    return FileResponse(
        storage.path(movimiento.foto_key),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )

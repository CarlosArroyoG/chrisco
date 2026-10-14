"""Bloqueos de equipos que pone el personal: mantenimiento programado u otra razón."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, DbSession, StaffUser
from app.schemas.disponibilidad import BloqueoIn, BloqueoOut
from app.services import disponibilidad, equipos

router = APIRouter(tags=["bloqueos"])


@router.get("/admin/equipos/{equipo_id}/bloqueos", response_model=list[BloqueoOut])
def list_bloqueos(_: StaffUser, equipo_id: uuid.UUID, db: DbSession) -> list[BloqueoOut]:
    """Bloqueos vigentes y futuros del equipo (rentas, reservas provisionales y del personal)."""
    equipos.get_equipo(db, equipo_id)
    return disponibilidad.upcoming(db, equipo_id)


@router.post(
    "/admin/equipos/{equipo_id}/bloqueos",
    response_model=BloqueoOut,
    status_code=status.HTTP_201_CREATED,
)
def create_bloqueo(
    admin: AdminUser, equipo_id: uuid.UUID, body: BloqueoIn, db: DbSession
) -> BloqueoOut:
    equipo = equipos.get_equipo(db, equipo_id)
    bloqueo = disponibilidad.block(
        db, equipo, body.tipo, body.desde, body.hasta, body.motivo, admin
    )
    return disponibilidad.to_out(bloqueo)


@router.post("/admin/bloqueos/{bloqueo_id}/liberar", status_code=status.HTTP_204_NO_CONTENT)
def release_bloqueo(_: AdminUser, bloqueo_id: uuid.UUID, db: DbSession) -> None:
    disponibilidad.release_staff_block(db, bloqueo_id)

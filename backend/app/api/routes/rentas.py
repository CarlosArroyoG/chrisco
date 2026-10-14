"""Solicitudes de renta. Los clientes ven y manejan las de su empresa; el personal ve todas."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ApprovedClientUser, CatalogUser, DbSession, company_of
from app.models.renta import RentaEstado
from app.schemas.common import Page
from app.schemas.renta import PreviewOut, RentaOut, SolicitudCreada, SolicitudIn, WhatsappOut
from app.services import rentas

router = APIRouter(prefix="/rentas", tags=["rentas"])


@router.post("/solicitudes/preview", response_model=PreviewOut)
def preview_solicitud(_: ApprovedClientUser, body: SolicitudIn, db: DbSession) -> PreviewOut:
    """Qué se le pedirá al cliente y si el equipo está libre; no reserva nada."""
    return rentas.preview(db, body)


@router.post("/solicitudes", response_model=SolicitudCreada, status_code=status.HTTP_201_CREATED)
def create_solicitud(user: ApprovedClientUser, body: SolicitudIn, db: DbSession) -> SolicitudCreada:
    """Reserva el equipo 20 minutos y devuelve el mensaje listo para mandar a ventas."""
    renta = rentas.create_request(db, user, company_of(user), body)
    return SolicitudCreada(**rentas.to_out(renta).model_dump(), whatsapp=rentas.whatsapp_for(renta))


@router.get("", response_model=Page[RentaOut])
def list_rentas(
    user: CatalogUser,
    db: DbSession,
    estado: RentaEstado | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RentaOut]:
    items, total = rentas.list_for(db, user, estado=estado, q=q, limit=limit, offset=offset)
    return Page(items=[rentas.to_out(r) for r in items], total=total)


@router.get("/{renta_id}", response_model=RentaOut)
def get_renta(user: CatalogUser, renta_id: uuid.UUID, db: DbSession) -> RentaOut:
    return rentas.to_out(rentas.get_for_user(db, user, renta_id))


@router.get("/{renta_id}/whatsapp", response_model=WhatsappOut)
def get_whatsapp(user: CatalogUser, renta_id: uuid.UUID, db: DbSession) -> WhatsappOut:
    """El mensaje de ventas de una solicitud, para reenviarlo si hace falta."""
    return rentas.whatsapp_for(rentas.get_for_user(db, user, renta_id))


@router.post("/{renta_id}/cancelar", response_model=RentaOut)
def cancel_renta(user: CatalogUser, renta_id: uuid.UUID, db: DbSession) -> RentaOut:
    renta = rentas.get_for_user(db, user, renta_id)
    return rentas.to_out(rentas.cancel(db, renta))

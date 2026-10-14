"""Cotización de una renta. Ventas cotiza; el cliente de la empresa acepta o rechaza."""

import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.api.deps import ApprovedClientUser, CatalogUser, DbSession, MailerDep, StaffUser
from app.schemas.cotizacion import CotizacionIn, CotizacionOut, CotizacionSugerida, MotivoIn
from app.schemas.renta import RentaOut
from app.services import accounts, cotizaciones, notifications, rentas

router = APIRouter(prefix="/rentas/{renta_id}", tags=["cotizaciones"])


@router.get("/cotizacion/sugerida", response_model=CotizacionSugerida)
def get_sugerida(user: StaffUser, renta_id: uuid.UUID, db: DbSession) -> CotizacionSugerida:
    return cotizaciones.suggested(rentas.get_for_user(db, user, renta_id))


@router.post("/cotizacion", response_model=CotizacionOut, status_code=status.HTTP_201_CREATED)
def create_cotizacion(
    staff: StaffUser,
    renta_id: uuid.UUID,
    body: CotizacionIn,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> CotizacionOut:
    renta = rentas.get_for_user(db, staff, renta_id)
    cotizacion = cotizaciones.create(db, renta, staff, body)
    background.add_task(mailer.send, notifications.quote_ready_mail(renta.solicitante, renta))
    return cotizaciones.to_out(cotizacion)


@router.get("/cotizacion", response_model=CotizacionOut)
def get_cotizacion(user: CatalogUser, renta_id: uuid.UUID, db: DbSession) -> CotizacionOut:
    renta = rentas.get_for_user(db, user, renta_id)
    return cotizaciones.to_out(cotizaciones.require_current(renta))


@router.post("/cotizacion/aceptar", response_model=RentaOut)
def accept_cotizacion(
    user: ApprovedClientUser,
    renta_id: uuid.UUID,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> RentaOut:
    """El cliente acepta: el equipo queda apartado 3 horas para que cumpla los requisitos."""
    renta = rentas.get_for_user(db, user, renta_id)
    cotizaciones.accept(db, renta, user)
    for staff in accounts.staff_users(db):
        background.add_task(mailer.send, notifications.quote_accepted_mail(staff, renta))
    return rentas.to_out(renta)


@router.post("/cotizacion/rechazar", response_model=RentaOut)
def decline_cotizacion(user: ApprovedClientUser, renta_id: uuid.UUID, db: DbSession) -> RentaOut:
    renta = rentas.get_for_user(db, user, renta_id)
    cotizaciones.decline(db, renta)
    return rentas.to_out(renta)


@router.post("/rechazar", response_model=RentaOut)
def reject_solicitud(
    staff: StaffUser,
    renta_id: uuid.UUID,
    body: MotivoIn,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> RentaOut:
    """Ventas no puede atender la solicitud: se libera el equipo y se avisa al cliente."""
    renta = rentas.get_for_user(db, staff, renta_id)
    cotizaciones.reject_request(db, renta, body.motivo)
    background.add_task(mailer.send, notifications.request_rejected_mail(renta.solicitante, renta))
    return rentas.to_out(renta)

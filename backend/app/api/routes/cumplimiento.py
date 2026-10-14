"""Requisitos del apartado: documentos, condiciones y pagos."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import (
    ApprovedClientUser,
    CatalogUser,
    DbSession,
    MailerDep,
    StaffUser,
    StorageDep,
)
from app.api.forms import PagoForm
from app.models.renta import Renta
from app.schemas.cumplimiento import (
    CondicionIn,
    CumplimientoOut,
    DocumentoOut,
    PagoOut,
    RevisionIn,
)
from app.services import cumplimiento, notifications, rentas
from app.services.mailer import Mailer
from app.services.storage import read_document_upload

router = APIRouter(prefix="/rentas/{renta_id}", tags=["cumplimiento"])


def _file(storage: StorageDep, key: str) -> FileResponse:
    media = "application/pdf" if key.endswith(".pdf") else "image/jpeg"
    return FileResponse(
        storage.path(key),
        media_type=media,
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )


def _notify_confirmed(
    confirmed: bool, renta: Renta, mailer: Mailer, background: BackgroundTasks
) -> None:
    if confirmed:
        background.add_task(
            mailer.send, notifications.rental_confirmed_mail(renta.solicitante, renta)
        )


@router.get("/cumplimiento", response_model=CumplimientoOut)
def get_cumplimiento(user: CatalogUser, renta_id: uuid.UUID, db: DbSession) -> CumplimientoOut:
    return cumplimiento.to_out(rentas.get_for_user(db, user, renta_id))


# ---------------------------------------------------------------------- documentos


@router.post("/documentos", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED)
def upload_documento(
    user: ApprovedClientUser,
    renta_id: uuid.UUID,
    requisito: Annotated[str, Form()],
    archivo: Annotated[UploadFile, File(description="PDF o foto del documento")],
    db: DbSession,
    storage: StorageDep,
) -> DocumentoOut:
    renta = rentas.get_for_user(db, user, renta_id)
    data, extension = read_document_upload(archivo)
    documento = cumplimiento.upload_document(
        db, storage, renta, user, requisito, data, extension, archivo.filename or "documento"
    )
    return cumplimiento.document_out(documento)


@router.get("/documentos/{doc_id}/archivo", response_class=FileResponse)
def download_documento(
    user: CatalogUser, renta_id: uuid.UUID, doc_id: uuid.UUID, db: DbSession, storage: StorageDep
) -> FileResponse:
    renta = rentas.get_for_user(db, user, renta_id)
    documento = cumplimiento.find(renta.documentos, doc_id, "Documento")
    return _file(storage, documento.key)


@router.post("/documentos/{doc_id}/revisar", response_model=CumplimientoOut)
def review_documento(
    staff: StaffUser,
    renta_id: uuid.UUID,
    doc_id: uuid.UUID,
    body: RevisionIn,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> CumplimientoOut:
    renta = rentas.get_for_user(db, staff, renta_id)
    documento, confirmed = cumplimiento.review_document(
        db, renta, doc_id, staff, body.aprobado, body.nota
    )
    if not body.aprobado:
        mail = notifications.document_rejected_mail(
            renta.solicitante, renta, documento.requisito, body.nota
        )
        background.add_task(mailer.send, mail)
    _notify_confirmed(confirmed, renta, mailer, background)
    return cumplimiento.to_out(renta)


# ---------------------------------------------------------------------- condiciones


@router.post("/condiciones/{codigo}", response_model=CumplimientoOut)
def set_condicion(
    staff: StaffUser,
    renta_id: uuid.UUID,
    codigo: str,
    body: CondicionIn,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> CumplimientoOut:
    renta = rentas.get_for_user(db, staff, renta_id)
    confirmed = cumplimiento.set_condicion(db, renta, codigo, body.cumplida)
    _notify_confirmed(confirmed, renta, mailer, background)
    return cumplimiento.to_out(renta)


# ---------------------------------------------------------------------- pagos


@router.post("/pagos", response_model=PagoOut, status_code=status.HTTP_201_CREATED)
def report_pago(
    user: ApprovedClientUser,
    renta_id: uuid.UUID,
    datos: PagoForm,
    comprobante: Annotated[UploadFile, File(description="Comprobante de la transferencia")],
    db: DbSession,
    storage: StorageDep,
) -> PagoOut:
    renta = rentas.get_for_user(db, user, renta_id)
    data, extension = read_document_upload(comprobante)
    return cumplimiento.payment_out(
        cumplimiento.report_payment(db, storage, renta, user, datos, data, extension)
    )


@router.get("/pagos/{pago_id}/comprobante", response_class=FileResponse)
def download_comprobante(
    user: CatalogUser, renta_id: uuid.UUID, pago_id: uuid.UUID, db: DbSession, storage: StorageDep
) -> FileResponse:
    renta = rentas.get_for_user(db, user, renta_id)
    pago = cumplimiento.find(renta.pagos, pago_id, "Pago")
    return _file(storage, pago.comprobante_key)


@router.post("/pagos/{pago_id}/revisar", response_model=CumplimientoOut)
def review_pago(
    staff: StaffUser,
    renta_id: uuid.UUID,
    pago_id: uuid.UUID,
    body: RevisionIn,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> CumplimientoOut:
    """`aprobado=true` confirma que el dinero llegó; `false` lo rechaza con un motivo."""
    renta = rentas.get_for_user(db, staff, renta_id)
    _, confirmed = cumplimiento.review_payment(db, renta, pago_id, staff, body.aprobado, body.nota)
    background.add_task(
        mailer.send,
        notifications.payment_reviewed_mail(renta.solicitante, renta, body.aprobado, body.nota),
    )
    _notify_confirmed(confirmed, renta, mailer, background)
    return cumplimiento.to_out(renta)

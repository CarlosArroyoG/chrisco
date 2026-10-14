"""Revisión de empresas por el personal. Ver y descargar: admin y ventas; decidir: solo admin."""

import uuid

from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession, MailerDep, StaffUser, StorageDep
from app.models.empresa import Empresa, EmpresaStatus
from app.schemas.empresa import EmpresaDetailOut, EmpresaListItem, RejectRequest, empresa_detail
from app.services import empresas, notifications

router = APIRouter(prefix="/admin/empresas", tags=["admin"])


@router.get("", response_model=list[EmpresaListItem])
def list_companies(
    _: StaffUser, db: DbSession, status_filter: EmpresaStatus | None = None
) -> list[EmpresaListItem]:
    query = select(Empresa).options(selectinload(Empresa.users)).order_by(Empresa.created_at.desc())
    if status_filter:
        query = query.where(Empresa.status == status_filter)
    return [EmpresaListItem.from_empresa(e) for e in db.scalars(query)]


@router.get("/{empresa_id}", response_model=EmpresaDetailOut)
def company_detail(_: StaffUser, empresa_id: uuid.UUID, db: DbSession) -> EmpresaDetailOut:
    return empresa_detail(empresas.get_empresa(db, empresa_id))


@router.get("/{empresa_id}/constancia", response_class=FileResponse)
def download_constancia(
    _: StaffUser, empresa_id: uuid.UUID, db: DbSession, storage: StorageDep
) -> FileResponse:
    empresa = empresas.get_empresa(db, empresa_id)
    return FileResponse(
        storage.path(empresa.constancia_key),
        media_type="application/pdf",
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )


@router.post("/{empresa_id}/aprobar", status_code=status.HTTP_204_NO_CONTENT)
def approve_company(
    admin: AdminUser,
    empresa_id: uuid.UUID,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> None:
    empresa = empresas.get_empresa(db, empresa_id)
    empresas.approve(db, empresa, admin)
    if owner := empresa.owner:
        background.add_task(mailer.send, notifications.company_approved_mail(owner, empresa))


@router.post("/{empresa_id}/rechazar", status_code=status.HTTP_204_NO_CONTENT)
def reject_company(
    admin: AdminUser,
    empresa_id: uuid.UUID,
    body: RejectRequest,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> None:
    empresa = empresas.get_empresa(db, empresa_id)
    empresas.reject(db, empresa, admin, body.motivo)
    if owner := empresa.owner:
        background.add_task(mailer.send, notifications.company_rejected_mail(owner, empresa))

"""Área de la empresa cliente: registro público, su estado y su equipo de usuarios."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Request, UploadFile, status

from app.api.deps import ClientUser, CompanyOwner, DbSession, MailerDep, StorageDep, company_of
from app.api.forms import CompanyForm, RegistroForm
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.common import MessageOut
from app.schemas.empresa import (
    CompanyUserOut,
    EmpresaDetailOut,
    InviteUserRequest,
    empresa_detail,
)
from app.services import empresas, notifications
from app.services.storage import read_pdf_upload

router = APIRouter(prefix="/empresa", tags=["empresa"])


@router.post("/registro", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def register(
    request: Request,
    data: RegistroForm,
    constancia: Annotated[UploadFile, File(description="Constancia de situación fiscal (PDF)")],
    db: DbSession,
    storage: StorageDep,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> MessageOut:
    pdf = read_pdf_upload(constancia)
    owner = empresas.register_company(db, storage, data, pdf)
    background.add_task(mailer.send, notifications.verification_mail(owner))
    return MessageOut(
        detail="Registro recibido. Confirma tu correo con el enlace que te enviamos; "
        "después revisaremos los datos de tu empresa."
    )


@router.get("/me", response_model=EmpresaDetailOut)
def my_company(user: ClientUser) -> EmpresaDetailOut:
    return empresa_detail(company_of(user))


@router.put("/me", response_model=EmpresaDetailOut)
def resubmit_company(
    owner: CompanyOwner,
    data: CompanyForm,
    constancia: Annotated[UploadFile, File(description="Constancia de situación fiscal (PDF)")],
    db: DbSession,
    storage: StorageDep,
) -> EmpresaDetailOut:
    """Tras un rechazo: corrige los datos y vuelve a la revisión."""
    pdf = read_pdf_upload(constancia)
    empresa = company_of(owner)
    empresas.resubmit(db, storage, empresa, data, pdf)
    return empresa_detail(empresa)


@router.post("/me/usuarios", response_model=CompanyUserOut, status_code=status.HTTP_201_CREATED)
def invite_user(
    owner: CompanyOwner,
    body: InviteUserRequest,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> User:
    empresa = company_of(owner)
    user = empresas.invite_user(db, empresa.id, owner, body.email, body.full_name)
    background.add_task(mailer.send, notifications.invitation_mail(user, empresa, owner))
    return user


@router.delete("/me/usuarios/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(owner: CompanyOwner, user_id: uuid.UUID, db: DbSession) -> None:
    empresas.remove_user(db, company_of(owner), user_id)

"""Personal de CHRISCO: altas, roles y bajas (solo administradores)."""

import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.api.deps import AdminUser, DbSession, MailerDep
from app.core.errors import Conflict
from app.schemas.personal import PersonalIn, PersonalOut, PersonalUpdate
from app.services import notifications, personal

router = APIRouter(prefix="/admin/personal", tags=["personal"])


@router.get("", response_model=list[PersonalOut])
def list_personal(_: AdminUser, db: DbSession) -> list[PersonalOut]:
    return [personal.to_out(u) for u in personal.listing(db)]


@router.post("", response_model=PersonalOut, status_code=status.HTTP_201_CREATED)
def create_personal(
    admin: AdminUser,
    body: PersonalIn,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> PersonalOut:
    user = personal.create(db, body)
    background.add_task(mailer.send, notifications.staff_invitation_mail(user, admin))
    return personal.to_out(user)


@router.put("/{user_id}", response_model=PersonalOut)
def update_personal(
    admin: AdminUser, user_id: uuid.UUID, body: PersonalUpdate, db: DbSession
) -> PersonalOut:
    target = personal.get_staff(db, user_id)
    return personal.to_out(personal.update(db, admin, target, body))


@router.post("/{user_id}/invitacion", status_code=status.HTTP_204_NO_CONTENT)
def resend_invitation(
    admin: AdminUser,
    user_id: uuid.UUID,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> None:
    """Reenvía el enlace para crear la contraseña a quien aún no la ha creado."""
    target = personal.get_staff(db, user_id)
    if target.email_verified_at is not None:
        raise Conflict("Esta persona ya creó su contraseña")
    if not target.is_active:
        raise Conflict("Esta persona está dada de baja")
    background.add_task(mailer.send, notifications.staff_invitation_mail(target, admin))

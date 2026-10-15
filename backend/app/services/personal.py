"""Gestión del personal de CHRISCO (admin, ventas, operador) desde la interfaz."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound
from app.models.user import Role, User
from app.schemas.personal import PersonalIn, PersonalOut, PersonalUpdate
from app.services import accounts

STAFF_ROLES = (Role.ADMIN, Role.VENTAS, Role.OPERADOR)


def to_out(user: User) -> PersonalOut:
    return PersonalOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,  # type: ignore[arg-type]  # solo se muestran roles del personal
        is_active=user.is_active,
        pendiente_invitacion=user.email_verified_at is None,
        created_at=user.created_at,
    )


def listing(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User).where(User.role.in_(STAFF_ROLES)).order_by(User.full_name, User.email)
        )
    )


def get_staff(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None or user.role not in STAFF_ROLES:
        raise NotFound("Persona no encontrada")
    return user


def create(db: Session, data: PersonalIn) -> User:
    """Da de alta a una persona sin contraseña: la crea ella con el enlace de la invitación."""
    if accounts.get_by_email(db, data.email) is not None:
        raise Conflict("Ya existe una cuenta con ese correo")
    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        role=Role(data.role),
        password_hash=accounts.unusable_password_hash(),
    )
    db.add(user)
    db.commit()
    return user


def update(db: Session, actor: User, target: User, data: PersonalUpdate) -> User:
    """Cambia el rol o la baja de alguien. Siempre debe quedar al menos un administrador activo."""
    # Bloquea a los administradores: dos cambios simultáneos no pueden dejar el sistema sin ninguno.
    admins = list(
        db.scalars(
            select(User).where(User.role == Role.ADMIN, User.is_active.is_(True)).with_for_update()
        )
    )
    db.refresh(target)
    new_role = Role(data.role) if data.role is not None else target.role
    new_active = target.is_active if data.is_active is None else data.is_active
    if target.id == actor.id and (new_role != target.role or not new_active):
        raise Conflict("No puedes cambiar tu propio rol ni darte de baja")
    loses_admin = (
        target.role == Role.ADMIN
        and target.is_active
        and (new_role != Role.ADMIN or not new_active)
    )
    if loses_admin and len(admins) <= 1:
        raise Conflict("Debe quedar al menos un administrador activo")
    if new_role != target.role or new_active != target.is_active:
        target.role = new_role
        target.is_active = new_active
        target.token_version += 1  # cierra sus sesiones: los permisos viajan en el rol
    db.commit()
    return target

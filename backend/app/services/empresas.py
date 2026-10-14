"""Reglas de negocio de las empresas cliente: alta, revisión del administrador y usuarios."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, InvalidInput, NotFound
from app.core.security import hash_password
from app.models.empresa import Empresa, EmpresaStatus
from app.models.user import Role, User
from app.schemas.empresa import CompanyData, RegistroEmpresaForm
from app.services import accounts
from app.services.storage import PrivateStorage

_DUPLICATE = "Ya existe una cuenta o una empresa registrada con esos datos"


def _ensure_unique(
    db: Session, rfc: str, *, email: str | None = None, own_id: uuid.UUID | None = None
) -> None:
    taken = select(Empresa.id).where(Empresa.rfc == rfc)
    if own_id:
        taken = taken.where(Empresa.id != own_id)
    if db.scalar(taken):
        raise Conflict("Ya hay una empresa registrada con ese RFC")
    if email and accounts.get_by_email(db, email):
        raise Conflict("Ya existe una cuenta con ese correo")


def register_company(
    db: Session, storage: PrivateStorage, data: RegistroEmpresaForm, pdf: bytes
) -> User:
    """Crea la empresa (pendiente de revisión) y a su titular (con el correo por verificar)."""
    _ensure_unique(db, data.rfc, email=data.email)
    key = storage.save_pdf(pdf)
    empresa = Empresa(
        razon_social=data.razon_social,
        sitio_web=data.sitio_web,
        rfc=data.rfc,
        constancia_key=key,
    )
    owner = User(
        email=data.email.lower(),
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=Role.CLIENTE,
        empresa=empresa,
        is_company_owner=True,
    )
    db.add_all([empresa, owner])
    try:
        db.commit()
    except IntegrityError:  # otra solicitud ganó la carrera por el mismo RFC o correo
        db.rollback()
        storage.delete(key)
        raise Conflict(_DUPLICATE) from None
    return owner


def get_empresa(db: Session, empresa_id: uuid.UUID) -> Empresa:
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise NotFound("Empresa no encontrada")
    return empresa


def active_user_count(db: Session, empresa_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.empresa_id == empresa_id, User.is_active)
        )
        or 0
    )


def approve(db: Session, empresa: Empresa, reviewer: User) -> None:
    if empresa.status != EmpresaStatus.PENDIENTE:
        raise Conflict("Solo se puede aprobar una empresa pendiente de revisión")
    _review(db, empresa, reviewer, EmpresaStatus.APROBADA, None)


def reject(db: Session, empresa: Empresa, reviewer: User, motivo: str) -> None:
    if empresa.status != EmpresaStatus.PENDIENTE:
        raise Conflict("Solo se puede rechazar una empresa pendiente de revisión")
    _review(db, empresa, reviewer, EmpresaStatus.RECHAZADA, motivo)


def _review(
    db: Session, empresa: Empresa, reviewer: User, status: EmpresaStatus, motivo: str | None
) -> None:
    empresa.status = status
    empresa.motivo_rechazo = motivo
    empresa.reviewed_by_id = reviewer.id
    empresa.reviewed_at = datetime.now(UTC)
    db.commit()


def resubmit(
    db: Session, storage: PrivateStorage, empresa: Empresa, data: CompanyData, pdf: bytes
) -> None:
    """Tras un rechazo, la empresa corrige sus datos y vuelve a la cola de revisión."""
    if empresa.status != EmpresaStatus.RECHAZADA:
        raise Conflict("Solo una empresa rechazada puede reenviar sus datos")
    _ensure_unique(db, data.rfc, own_id=empresa.id)
    old_key = empresa.constancia_key
    new_key = storage.save_pdf(pdf)
    empresa.razon_social = data.razon_social
    empresa.sitio_web = data.sitio_web
    empresa.rfc = data.rfc
    empresa.constancia_key = new_key
    empresa.status = EmpresaStatus.PENDIENTE
    empresa.motivo_rechazo = None
    empresa.reviewed_by_id = None
    empresa.reviewed_at = None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        storage.delete(new_key)
        raise Conflict(_DUPLICATE) from None
    storage.delete(old_key)


def invite_user(
    db: Session, empresa_id: uuid.UUID, owner: User, email: str, full_name: str
) -> User:
    """Crea un usuario invitado en la empresa. Respeta el máximo de usuarios activos."""
    # Bloquea la fila de la empresa: dos invitaciones simultáneas no pueden pasar del límite.
    empresa = db.scalar(select(Empresa).where(Empresa.id == empresa_id).with_for_update())
    if empresa is None or empresa.status != EmpresaStatus.APROBADA:
        raise Forbidden("Tu empresa debe estar aprobada para invitar usuarios")
    limit = get_settings().max_users_per_company
    if active_user_count(db, empresa.id) >= limit:
        raise Conflict(f"Tu empresa ya tiene el máximo de {limit} usuarios")
    existing = accounts.get_by_email(db, email)
    if existing is None:
        user = User(
            email=email.lower(),
            full_name=full_name,
            password_hash=accounts.unusable_password_hash(),
            role=Role.CLIENTE,
            empresa_id=empresa.id,
        )
        db.add(user)
    elif existing.empresa_id == empresa.id and not existing.is_active:
        # Reincorpora a alguien que había sido dado de baja de esta misma empresa.
        user = existing
        user.full_name = full_name
        user.password_hash = accounts.unusable_password_hash()
        user.email_verified_at = None
        user.token_version += 1
        user.is_active = True
    else:
        raise Conflict("Ya existe una cuenta con ese correo")
    db.commit()
    return user


def remove_user(db: Session, empresa: Empresa, user_id: uuid.UUID) -> None:
    """Da de baja a un usuario y libera su lugar. Al titular no se le puede dar de baja."""
    target = next((u for u in empresa.users if u.id == user_id), None)
    if target is None:
        raise NotFound("Usuario no encontrado en tu empresa")
    if target.is_company_owner:
        raise InvalidInput("No se puede dar de baja al titular de la empresa")
    target.is_active = False
    target.token_version += 1  # cierra sus sesiones abiertas
    db.commit()

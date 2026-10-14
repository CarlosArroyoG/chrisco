from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.empresa import Empresa, EmpresaStatus
from app.models.user import Role, User
from app.services import accounts
from app.services.mailer import Mailer, get_mailer
from app.services.storage import PrivateStorage, get_storage

DbSession = Annotated[Session, Depends(get_db)]
MailerDep = Annotated[Mailer, Depends(get_mailer)]
StorageDep = Annotated[PrivateStorage, Depends(get_storage)]
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    user = accounts.user_from_token(db, credentials.credentials, "access") if credentials else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    """Dependencia que exige que el usuario tenga alguno de los roles dados."""

    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes permiso para esta acción")
        return user

    return checker


def company_of(user: User) -> Empresa:
    """Empresa de un usuario cliente (la restricción de la BD garantiza que existe)."""
    assert user.empresa is not None
    return user.empresa


ClientUser = Annotated[User, Depends(require_roles(Role.CLIENTE))]


def require_approved_company(user: ClientUser) -> User:
    """Cliente cuya empresa ya fue aprobada: el único que puede solicitar equipo."""
    if company_of(user).status != EmpresaStatus.APROBADA:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu empresa aún no está aprobada")
    return user


def require_company_owner(user: ClientUser) -> User:
    if not user.is_company_owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Solo el titular de la empresa puede hacer esto"
        )
    return user


ApprovedClientUser = Annotated[User, Depends(require_approved_company)]
CompanyOwner = Annotated[User, Depends(require_company_owner)]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(Role.ADMIN, Role.VENTAS))]

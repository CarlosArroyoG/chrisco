from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import Role, User

DbSession = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


def load_user_from_token(db: Session, token: str, token_type: str) -> User | None:
    """Usuario activo al que pertenece un token vigente; None si algo no cuadra."""
    decoded = decode_token(token, token_type)  # type: ignore[arg-type]
    if decoded is None:
        return None
    user_id, version = decoded
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.token_version != version:
        return None
    return user


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    user = load_user_from_token(db, credentials.credentials, "access") if credentials else None
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

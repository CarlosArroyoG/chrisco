from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, load_user_from_token
from app.core.limiter import limiter
from app.core.security import create_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_token(user.id, user.token_version, "access"),
        refresh_token=create_token(user.id, user.token_version, "refresh"),
    )


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: DbSession) -> TokenPair:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    password_ok = verify_password(body.password, user.password_hash if user else None)
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("30/minute")
def refresh(request: Request, body: RefreshRequest, db: DbSession) -> TokenPair:
    user = load_user_from_token(db, body.refresh_token, "refresh")
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada")
    return _issue_tokens(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: CurrentUser, db: DbSession) -> None:
    """Invalida todos los tokens vigentes del usuario (todos sus dispositivos)."""
    user.token_version += 1
    db.commit()

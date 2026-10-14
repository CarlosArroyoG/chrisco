from fastapi import APIRouter, BackgroundTasks, Request, status

from app.api.deps import CurrentUser, DbSession, MailerDep
from app.core.errors import Unauthorized
from app.core.limiter import limiter
from app.core.security import create_token
from app.models.user import User
from app.schemas.auth import (
    EmailRequest,
    LoginRequest,
    RefreshRequest,
    SetPasswordRequest,
    TokenPair,
    TokenRequest,
    UserOut,
)
from app.services import accounts, notifications

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_token(user.id, user.token_version, "access"),
        refresh_token=create_token(user.id, user.token_version, "refresh"),
    )


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: DbSession) -> TokenPair:
    return _issue_tokens(accounts.authenticate(db, body.email, body.password))


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("30/minute")
def refresh(request: Request, body: RefreshRequest, db: DbSession) -> TokenPair:
    user = accounts.user_from_token(db, body.refresh_token, "refresh")
    if user is None:
        raise Unauthorized("Sesión inválida o expirada")
    return _issue_tokens(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: CurrentUser, db: DbSession) -> None:
    """Invalida todos los tokens vigentes del usuario (todos sus dispositivos)."""
    user.token_version += 1
    db.commit()


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
def verify_email(request: Request, body: TokenRequest, db: DbSession) -> None:
    accounts.verify_email(db, body.token)


# Los dos siguientes responden siempre 204: no revelan si el correo está registrado.
@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def resend_verification(
    request: Request,
    body: EmailRequest,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> None:
    user = accounts.get_by_email(db, body.email)
    if user and user.is_active and user.email_verified_at is None:
        background.add_task(mailer.send, notifications.verification_mail(user))


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    body: EmailRequest,
    db: DbSession,
    mailer: MailerDep,
    background: BackgroundTasks,
) -> None:
    user = accounts.get_by_email(db, body.email)
    if user and user.is_active:
        background.add_task(mailer.send, notifications.password_reset_mail(user))


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def reset_password(request: Request, body: SetPasswordRequest, db: DbSession) -> None:
    accounts.set_password_from_token(db, body.token, "reset_password", body.password)


@router.post("/accept-invite", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def accept_invite(request: Request, body: SetPasswordRequest, db: DbSession) -> None:
    accounts.set_password_from_token(db, body.token, "invite", body.password)

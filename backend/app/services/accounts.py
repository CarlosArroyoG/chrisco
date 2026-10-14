"""Reglas de cuentas de usuario: autenticación, verificación de correo y contraseñas."""

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, InvalidInput, Unauthorized
from app.core.security import TokenType, decode_token, hash_password, verify_password
from app.models.user import User

INVALID_LINK = "El enlace no es válido o ya venció"


def user_from_token(db: Session, token: str, token_type: TokenType) -> User | None:
    """Usuario activo al que pertenece un token vigente; None si algo no cuadra."""
    decoded = decode_token(token, token_type)
    if decoded is None:
        return None
    user_id, version = decoded
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.token_version != version:
        return None
    return user


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def unusable_password_hash() -> str:
    """Hash de una contraseña aleatoria que nadie conoce (invitados que aún no eligen la suya)."""
    return hash_password(secrets.token_urlsafe(32))


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_by_email(db, email)
    password_ok = verify_password(password, user.password_hash if user else None)
    if user is None or not password_ok or not user.is_active:
        raise Unauthorized("Correo o contraseña incorrectos")
    # Se revisa después de la contraseña para no revelar qué correos existen.
    if user.email_verified_at is None:
        raise Forbidden("Confirma tu correo antes de iniciar sesión. Revisa tu bandeja de entrada.")
    return user


def verify_email(db: Session, token: str) -> None:
    user = user_from_token(db, token, "verify_email")
    if user is None:
        raise InvalidInput(INVALID_LINK)
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
        db.commit()


def set_password_from_token(db: Session, token: str, token_type: TokenType, password: str) -> None:
    """Fija la contraseña con un enlace de invitación o de recuperación (de un solo uso).

    Recibir el enlace en su correo demuestra que el usuario controla ese buzón, así que también
    queda verificado. Subir `token_version` invalida el enlace y cualquier sesión anterior.
    """
    user = user_from_token(db, token, token_type)
    if user is None:
        raise InvalidInput(INVALID_LINK)
    user.password_hash = hash_password(password)
    user.token_version += 1
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
    db.commit()

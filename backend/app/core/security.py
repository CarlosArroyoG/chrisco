import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

ALGORITHM = "HS256"
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

# access/refresh: sesión. Los demás son enlaces de un solo propósito enviados por correo.
TokenType = Literal["access", "refresh", "verify_email", "invite", "reset_password"]

_password_hash = PasswordHash.recommended()
# Hash de relleno: se verifica cuando el usuario no existe para que el tiempo de
# respuesta no revele si el correo está registrado.
_DUMMY_HASH = _password_hash.hash("password-de-relleno")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    return (
        _password_hash.verify(password, password_hash or _DUMMY_HASH) and password_hash is not None
    )


def _lifetime(token_type: TokenType) -> timedelta:
    settings = get_settings()
    return {
        "access": timedelta(minutes=settings.access_token_minutes),
        "refresh": timedelta(days=settings.refresh_token_days),
        "verify_email": timedelta(hours=settings.verify_email_hours),
        "invite": timedelta(days=settings.invite_days),
        "reset_password": timedelta(minutes=settings.reset_password_minutes),
    }[token_type]


def create_token(user_id: uuid.UUID, token_version: int, token_type: TokenType) -> str:
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "type": token_type,
        "exp": datetime.now(UTC) + _lifetime(token_type),
    }
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: TokenType) -> tuple[uuid.UUID, int] | None:
    """Devuelve (user_id, token_version) si el token es válido y del tipo esperado."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            return None
        return uuid.UUID(payload["sub"]), int(payload["ver"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

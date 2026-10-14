import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]

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


def create_token(user_id: uuid.UUID, token_version: int, token_type: TokenType) -> str:
    settings = get_settings()
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "type": token_type,
        "exp": datetime.now(UTC) + lifetime,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: TokenType) -> tuple[uuid.UUID, int] | None:
    """Devuelve (user_id, token_version) si el token es válido y del tipo esperado."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            return None
        return uuid.UUID(payload["sub"]), int(payload["ver"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

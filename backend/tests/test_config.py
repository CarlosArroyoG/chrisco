"""La configuración de producción no arranca con valores de desarrollo."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = {
    "database_url": "postgresql+psycopg://u:p@db/chrisco",
    "secret_key": "x" * 40,
}
PRODUCCION = {
    **BASE,
    "environment": "production",
    "mail_backend": "smtp",
    "frontend_url": "https://go.chrisco.example",
    "cors_origins": ["https://go.chrisco.example"],
    "rate_limit_enabled": True,  # las pruebas lo apagan por entorno: aquí se fija
}


def make(**campos: Any) -> Settings:
    """Settings solo con lo indicado: `model_validate` no lee el entorno ni el .env."""
    return Settings.model_validate(campos)


def settings(**cambios: Any) -> Settings:
    return make(**{**PRODUCCION, **cambios})


def test_desarrollo_acepta_los_valores_por_defecto() -> None:
    assert make(**BASE).environment == "development"


def test_produccion_correcta_arranca() -> None:
    assert settings().environment == "production"


@pytest.mark.parametrize(
    ("cambio", "fragmento"),
    [
        ({"mail_backend": "console"}, "MAIL_BACKEND"),
        ({"mail_backend": "file"}, "MAIL_BACKEND"),
        ({"frontend_url": "http://go.chrisco.example"}, "FRONTEND_URL"),
        ({"cors_origins": ["http://localhost:4200"]}, "CORS_ORIGINS"),
        ({"rate_limit_enabled": False}, "RATE_LIMIT_ENABLED"),
    ],
)
def test_produccion_rechaza_valores_inseguros(cambio: dict[str, Any], fragmento: str) -> None:
    with pytest.raises(ValidationError, match=fragmento):
        settings(**cambio)


def test_lista_todos_los_problemas_juntos() -> None:
    with pytest.raises(ValidationError) as error:
        settings(mail_backend="console", frontend_url="http://x")
    assert "MAIL_BACKEND" in str(error.value) and "FRONTEND_URL" in str(error.value)


def test_la_clave_secreta_debe_ser_larga() -> None:
    with pytest.raises(ValidationError):
        settings(secret_key="corta")

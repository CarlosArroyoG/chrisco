from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str
    secret_key: str = Field(min_length=32)
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    verify_email_hours: int = 48
    invite_days: int = 7
    reset_password_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:4200"]
    rate_limit_enabled: bool = True

    # URL pública del frontend: se usa para armar los enlaces de los correos.
    frontend_url: str = "http://localhost:4200"

    # Archivos privados (constancias, licencias...). Nunca se sirven de forma pública.
    uploads_dir: Path = Path("uploads")
    max_upload_mb: int = 5

    # Correo: "console" escribe el mensaje en el log (desarrollo); "smtp" lo envía de verdad.
    mail_backend: str = "console"
    mail_from: str = "CHRISCO Go <no-responder@chrisco.example>"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True

    # Máximo de usuarios activos por empresa cliente.
    max_users_per_company: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # los valores vienen del entorno / .env

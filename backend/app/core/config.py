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

    # Correo: "console" escribe el mensaje en el log y "file" lo agrega a `mail_outbox_file`
    # (desarrollo y pruebas E2E); "smtp" lo envía de verdad.
    mail_backend: str = "console"
    mail_outbox_file: Path = Path("outbox.jsonl")
    mail_from: str = "CHRISCO Go <no-responder@chrisco.example>"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True

    # Cuánto dura una reserva provisional del equipo (ver `app.models.bloqueo`).
    hold_solicitud_minutes: int = 20
    hold_apartado_minutes: int = 180

    # Máximo de usuarios activos por empresa cliente.
    max_users_per_company: int = 3

    # Solicitudes de renta: cuántas puede tener abiertas una empresa a la vez (evita acaparar
    # equipos con reservas provisionales) y a quién se le manda el mensaje de WhatsApp.
    max_active_requests_per_company: int = 3
    sales_whatsapp_number: str = ""  # solo dígitos con código de país, p. ej. 5217221234567
    timezone: str = "America/Mexico_City"  # para mostrar fechas en los mensajes


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # los valores vienen del entorno / .env

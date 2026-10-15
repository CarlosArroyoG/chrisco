from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def today() -> date:
    """Hoy en la zona horaria del negocio (no la del servidor)."""
    return datetime.now(ZoneInfo(get_settings().timezone)).date()

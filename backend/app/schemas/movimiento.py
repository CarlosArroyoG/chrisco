import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.movimiento import MovimientoTipo
from app.schemas.common import Hours


class MovimientoIn(BaseModel):
    """Lo que captura el personal al entregar o recibir un equipo (con la foto del tablero)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: MovimientoTipo
    horometro: Hours
    notas: Annotated[str, StringConstraints(max_length=300)] | None = None


class MovimientoOut(BaseModel):
    id: uuid.UUID
    tipo: MovimientoTipo
    horometro: Hours
    notas: str | None
    registrado_por_nombre: str
    created_at: datetime


class MovimientosOut(BaseModel):
    movimientos: list[MovimientoOut]
    # Horas que marcó el equipo entre la salida y el regreso; None mientras no regrese.
    horas_usadas: Hours | None

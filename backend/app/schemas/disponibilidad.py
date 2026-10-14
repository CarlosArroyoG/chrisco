import enum
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints, model_validator

from app.models.bloqueo import BloqueoEstado, BloqueoTipo

MAX_BLOCK_DAYS = 366


class EstadoActual(enum.StrEnum):
    """Situación de un equipo en este momento, para quien administra la flota."""

    LIBRE = "libre"
    BLOQUEADO = "bloqueado"  # reserva provisional o apartado del personal
    RENTADO = "rentado"
    MANTENIMIENTO = "mantenimiento"
    BAJA = "baja"


class Periodo(BaseModel):
    """Rango [desde, hasta): el equipo vuelve a estar libre justo en `hasta`."""

    desde: AwareDatetime
    hasta: AwareDatetime

    @model_validator(mode="after")
    def _valid_range(self) -> "Periodo":
        if self.hasta <= self.desde:
            raise ValueError("La fecha final debe ser posterior a la inicial")
        if self.hasta - self.desde > timedelta(days=MAX_BLOCK_DAYS):
            raise ValueError(f"El periodo no puede pasar de {MAX_BLOCK_DAYS} días")
        return self


class BloqueoIn(Periodo):
    """Bloqueo que pone el personal: mantenimiento programado u otra razón."""

    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: Literal[BloqueoTipo.MANTENIMIENTO, BloqueoTipo.MANUAL]
    motivo: Annotated[str, StringConstraints(min_length=3, max_length=300)]

    @model_validator(mode="after")
    def _not_in_the_past(self) -> "BloqueoIn":
        if self.hasta <= datetime.now(UTC):
            raise ValueError("El bloqueo debe terminar en el futuro")
        return self


class BloqueoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    equipo_id: uuid.UUID
    tipo: BloqueoTipo
    estado: BloqueoEstado
    desde: datetime
    hasta: datetime
    vence_en: datetime | None
    motivo: str | None
    creado_por_nombre: str | None


class Ocupacion(BaseModel):
    """Un periodo ocupado, sin decir por qué (es lo único que ve un cliente)."""

    desde: datetime
    hasta: datetime


class DisponibilidadOut(BaseModel):
    disponible: bool
    desde: datetime
    hasta: datetime
    ocupado: list[Ocupacion]

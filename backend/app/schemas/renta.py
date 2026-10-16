import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.models.renta import OperadorModo, RentaEstado, Transporte
from app.schemas.common import Money
from app.schemas.disponibilidad import Periodo

MIN_HOURS = 1
START_TOLERANCE = timedelta(minutes=5)  # margen por el reloj del navegador


class Requisito(BaseModel):
    """Algo que el cliente debe cumplir o saber antes de que se confirme la renta."""

    codigo: str
    titulo: str
    detalle: str
    tipo: Literal["documento", "condicion", "cargo"]
    obligatorio: bool = True


class SolicitudIn(Periodo):
    """Lo que captura el cliente al pedir un equipo."""

    model_config = ConfigDict(str_strip_whitespace=True)

    equipo_id: uuid.UUID
    destino: Annotated[str, StringConstraints(min_length=5, max_length=200)]
    operador_modo: OperadorModo
    transporte: Transporte
    notas: Annotated[str, StringConstraints(max_length=500)] | None = None

    @model_validator(mode="after")
    def _future_and_long_enough(self) -> "SolicitudIn":
        if self.desde < datetime.now(UTC) - START_TOLERANCE:
            raise ValueError("El periodo debe empezar en el futuro")
        if self.hasta - self.desde < timedelta(hours=MIN_HOURS):
            raise ValueError(f"La renta mínima es de {MIN_HOURS} hora")
        return self


class PreviewOut(BaseModel):
    """Lo que verá el cliente antes de enviar: si está libre y qué se le va a pedir."""

    disponible: bool
    requisitos: list[Requisito]


class RentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    folio: str
    estado: RentaEstado
    empresa_id: uuid.UUID
    empresa_razon_social: str
    solicitante_nombre: str
    equipo_id: uuid.UUID
    equipo_codigo: str
    equipo_nombre: str
    # Primera foto del equipo y total de la cotización viva, para mostrar la renta como tarjeta.
    equipo_foto_id: uuid.UUID | None
    total: Money | None
    desde: datetime
    hasta: datetime
    destino: str
    operador_modo: OperadorModo
    transporte: Transporte
    notas: str | None
    requisitos: list[Requisito]
    # Mientras sigue reservada de forma provisional: cuándo se libera el equipo si nadie avanza.
    vence_en: datetime | None
    # Por qué terminó sin avanzar (rechazada por ventas o cancelada con motivo).
    motivo_cierre: str | None
    created_at: datetime


class WhatsappOut(BaseModel):
    """Mensaje para el agente de ventas. `url` es None si aún no se configura su número."""

    mensaje: str
    url: str | None


class SolicitudCreada(RentaOut):
    whatsapp: WhatsappOut

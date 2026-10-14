import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.cotizacion import CotizacionEstado, PartidaConcepto, PartidaUnidad
from app.schemas.common import Money, Quantity


class PartidaIn(BaseModel):
    """Un renglón de la cotización: renta, flete, operador, combustible…"""

    model_config = ConfigDict(str_strip_whitespace=True)

    concepto: PartidaConcepto
    descripcion: Annotated[str, StringConstraints(min_length=3, max_length=200)]
    cantidad: Quantity
    unidad: PartidaUnidad
    precio_unitario: Money


class PartidaOut(PartidaIn):
    model_config = ConfigDict(from_attributes=True)

    importe: Money


class CotizacionIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    partidas: Annotated[list[PartidaIn], Field(min_length=1, max_length=30)]
    # Si no se indica, se usa el porcentaje por defecto sobre el total.
    anticipo_monto: Money | None = None
    # Cuántas horas puede aceptarla el cliente; por defecto, la configurada.
    valida_horas: Annotated[int, Field(ge=1, le=168)] | None = None
    notas: Annotated[str, StringConstraints(max_length=500)] | None = None


class CotizacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    renta_id: uuid.UUID
    version: int
    estado: CotizacionEstado
    partidas: list[PartidaOut]
    subtotal: Money
    iva: Money
    total: Money
    anticipo_monto: Money
    valida_hasta: datetime
    notas: str | None
    creada_por_nombre: str | None
    created_at: datetime


class CotizacionCalculo(BaseModel):
    """Lo que dará la cotización con estos renglones, sin guardar nada."""

    importes: list[Money]
    subtotal: Money
    iva: Money
    total: Money
    anticipo_monto: Money


class CotizacionSugerida(BaseModel):
    """Punto de partida para que ventas cotice: renglones sugeridos y las reglas vigentes."""

    partidas: list[PartidaIn]
    iva_rate: float
    anticipo_default_percent: int
    valida_horas: int


class MotivoIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    motivo: Annotated[str, StringConstraints(min_length=5, max_length=500)]

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.gasto import GastoCategoria
from app.schemas.common import Money, Quantity


class GastoIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    fecha: date
    categoria: GastoCategoria
    concepto: Annotated[str, StringConstraints(min_length=3, max_length=120)]
    monto: Quantity
    equipo_id: uuid.UUID | None = None


class GastoOut(BaseModel):
    id: uuid.UUID
    fecha: date
    categoria: GastoCategoria
    concepto: str
    monto: Money
    equipo_codigo: str | None
    equipo_nombre: str | None
    registrado_por_nombre: str
    created_at: datetime


class GastosOut(BaseModel):
    items: list[GastoOut]
    total: int
    # Suma de todo lo que cumple el filtro (no solo de la página).
    suma: Money

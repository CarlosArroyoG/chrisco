from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer


class MessageOut(BaseModel):
    detail: str


class Page[T](BaseModel):
    """Una página de resultados y el total que cumple el filtro."""

    items: list[T]
    total: int


# Los importes y las horas se guardan como Decimal (sin errores de redondeo) pero viajan en el
# JSON como número, que es lo que espera el frontend.
_as_number = PlainSerializer(float, return_type=float, when_used="json")
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2), _as_number]
Hours = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=1), _as_number]

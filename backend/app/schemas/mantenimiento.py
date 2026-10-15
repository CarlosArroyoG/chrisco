import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.common import Hours, PositiveHours, SignedHours

Estado = Literal["ok", "proximo", "vencido"]


class PlanIn(BaseModel):
    """Un servicio periódico: se indica cada cuántas horas, cada cuántos días, o ambos."""

    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: Annotated[str, StringConstraints(min_length=3, max_length=80)]
    cada_horas: PositiveHours | None = None
    cada_dias: Annotated[int, Field(ge=1, le=3650)] | None = None
    activo: bool = True

    @model_validator(mode="after")
    def _some_interval(self) -> "PlanIn":
        if self.cada_horas is None and self.cada_dias is None:
            raise ValueError("Indica cada cuántas horas o cada cuántos días se repite")
        return self


class RealizadoIn(BaseModel):
    """El servicio se hizo; sin fecha ni horómetro se toman los de hoy y los del equipo."""

    model_config = ConfigDict(str_strip_whitespace=True)

    fecha: date | None = None
    horometro: Hours | None = None
    notas: Annotated[str, StringConstraints(max_length=300)] | None = None


class PlanOut(BaseModel):
    id: uuid.UUID
    equipo_id: uuid.UUID
    nombre: str
    cada_horas: PositiveHours | None
    cada_dias: int | None
    ultimo_horometro: Hours
    ultima_fecha: date
    activo: bool
    estado: Estado
    # Cuánto falta (negativo si ya se pasó); None si el plan no usa ese intervalo.
    faltan_horas: SignedHours | None
    faltan_dias: int | None


class AtencionItem(PlanOut):
    equipo_codigo: str
    equipo_nombre: str
    horometro_actual: Hours


class RegistroOut(BaseModel):
    id: uuid.UUID
    fecha: date
    horometro: Hours
    notas: str | None
    registrado_por_nombre: str
    created_at: datetime

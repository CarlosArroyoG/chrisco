import enum
import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.equipo import EquipoStatus
from app.models.renta import RentaEstado
from app.schemas.common import Hours, Money
from app.schemas.disponibilidad import EstadoActual

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_CODIGO_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,29}$")


class SpecFieldType(enum.StrEnum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"


class SpecField(BaseModel):
    """Definición de una especificación que una categoría pide a sus equipos."""

    model_config = ConfigDict(str_strip_whitespace=True)

    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
    label: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    type: SpecFieldType
    unit: Annotated[str, StringConstraints(max_length=12)] | None = None
    options: list[Annotated[str, StringConstraints(min_length=1, max_length=60)]] = []
    required: bool = False

    @model_validator(mode="after")
    def _options_only_for_select(self) -> "SpecField":
        if self.type == SpecFieldType.SELECT:
            if len(set(self.options)) < 2 or len(set(self.options)) != len(self.options):
                raise ValueError("Un campo de opciones necesita al menos 2 opciones distintas")
        elif self.options:
            raise ValueError("Solo los campos de opciones llevan lista de opciones")
        return self


class CategoriaIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: Annotated[str, StringConstraints(min_length=2, max_length=80)]
    spec_fields: list[SpecField] = Field(default_factory=list, max_length=30)

    @field_validator("spec_fields")
    @classmethod
    def _unique_keys(cls, fields: list[SpecField]) -> list[SpecField]:
        keys = [f.key for f in fields]
        if len(set(keys)) != len(keys):
            raise ValueError("Las especificaciones no pueden repetir su clave")
        return fields


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    spec_fields: list[SpecField]


class CategoriaAdminOut(CategoriaOut):
    equipos_count: int


class EquipoIn(BaseModel):
    """Datos editables de un equipo. Los comparten el alta, la edición y la importación CSV."""

    model_config = ConfigDict(str_strip_whitespace=True)

    codigo: str
    categoria_id: uuid.UUID
    nombre: Annotated[str, StringConstraints(min_length=2, max_length=120)]
    marca: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    modelo: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    numero_serie: Annotated[str, StringConstraints(min_length=2, max_length=60)]
    anio: Annotated[int, Field(ge=1950, le=2100)] | None = None
    horometro: Hours = Decimal(0)
    patio: Annotated[str, StringConstraints(min_length=2, max_length=80)] = "Patio Toluca CHRISCO"
    tarifa_hora: Annotated[Money, Field(gt=0)] | None = None
    tarifa_dia: Annotated[Money, Field(gt=0)] | None = None
    requiere_lowboy: bool = False
    requiere_operador_certificado: bool = False
    descripcion: Annotated[str, StringConstraints(max_length=2000)] | None = None
    notas: Annotated[str, StringConstraints(max_length=1000)] | None = None
    specs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("codigo")
    @classmethod
    def _codigo(cls, value: str) -> str:
        code = value.upper()
        if not _CODIGO_RE.match(code):
            raise ValueError("El código usa letras, números y guiones (2 a 30 caracteres)")
        return code

    @model_validator(mode="after")
    def _at_least_one_rate(self) -> "EquipoIn":
        if self.tarifa_hora is None and self.tarifa_dia is None:
            raise ValueError("Captura la tarifa por hora, por día o ambas")
        return self


class EquipoUpdate(EquipoIn):
    status: EquipoStatus = EquipoStatus.ACTIVO


class FotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int


class EquipoOut(BaseModel):
    """Vista completa para el personal. Solo describe datos: no revalida las reglas de entrada."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    categoria_id: uuid.UUID
    categoria_nombre: str
    nombre: str
    marca: str
    modelo: str
    numero_serie: str
    anio: int | None
    horometro: Hours
    patio: str
    tarifa_hora: Money | None
    tarifa_dia: Money | None
    requiere_lowboy: bool
    requiere_operador_certificado: bool
    descripcion: str | None
    notas: str | None
    specs: dict[str, Any]
    status: EquipoStatus
    estado_actual: EstadoActual
    fotos: list[FotoOut]
    created_at: datetime
    updated_at: datetime


class SpecValueOut(BaseModel):
    label: str
    value: str
    unit: str | None


class MiRenta(BaseModel):
    """Una renta abierta de la empresa del cliente sobre un equipo."""

    id: uuid.UUID
    folio: str
    estado: RentaEstado


class EquipoCatalogOut(BaseModel):
    """Vista para clientes: sin número de serie, horómetro ni notas internas."""

    id: uuid.UUID
    codigo: str
    nombre: str
    marca: str
    modelo: str
    anio: int | None
    categoria_id: uuid.UUID
    categoria_nombre: str
    patio: str
    tarifa_hora: Money | None
    tarifa_dia: Money | None
    requiere_lowboy: bool
    requiere_operador_certificado: bool
    descripcion: str | None
    specs: list[SpecValueOut]
    fotos: list[FotoOut]
    # Situación del equipo ahora mismo (libre, rentado, apartado…), para verlo de un vistazo.
    situacion: EstadoActual = EstadoActual.LIBRE
    # Solo se llena cuando se consulta un periodo concreto (`desde` y `hasta`).
    disponible: bool | None = None
    # La renta abierta de la empresa del cliente con este equipo, si la hay: decide el botón.
    mi_renta: MiRenta | None = None


class RowError(BaseModel):
    row: int
    message: str


class ImportResult(BaseModel):
    dry_run: bool
    rows: int
    created: int
    errors: list[RowError]

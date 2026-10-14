import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.models.cumplimiento import RevisionEstado
from app.models.renta import RentaEstado
from app.schemas.common import Money, Quantity
from app.schemas.renta import Requisito

Situacion = Literal["pendiente", "en_revision", "rechazado", "cumplido"]


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requisito: str
    filename: str
    estado: RevisionEstado
    nota_revision: str | None
    subido_por_nombre: str
    created_at: datetime
    revisado_at: datetime | None


class PagoIn(BaseModel):
    """Lo que captura el cliente al reportar una transferencia (junto con el comprobante)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    monto: Quantity
    fecha_pago: date
    referencia: Annotated[str, StringConstraints(max_length=60)] | None = None


class PagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monto: Money
    fecha_pago: date
    referencia: str | None
    estado: RevisionEstado
    nota_revision: str | None
    reportado_por_nombre: str
    created_at: datetime
    revisado_at: datetime | None


class RevisionIn(BaseModel):
    """Decisión del personal sobre un documento (aprobar o rechazar) o un pago (confirmar o no)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    aprobado: bool
    nota: Annotated[str, StringConstraints(max_length=300)] | None = None

    @model_validator(mode="after")
    def _reason_when_rejecting(self) -> "RevisionIn":
        if not self.aprobado and (self.nota is None or len(self.nota) < 3):
            raise ValueError("Explica el motivo del rechazo")
        return self


class CondicionIn(BaseModel):
    cumplida: bool


class ChecklistItem(Requisito):
    """Un requisito con su situación actual."""

    situacion: Situacion


class CumplimientoOut(BaseModel):
    checklist: list[ChecklistItem]
    documentos: list[DocumentoOut]
    pagos: list[PagoOut]
    total: Money | None  # de la cotización aceptada
    anticipo_requerido: Money | None
    pagado: Money  # pagos ya confirmados
    saldo: Money | None
    confirmada: bool  # la renta ya cumplió todo y quedó firme


class CobranzaItem(BaseModel):
    renta_id: uuid.UUID
    folio: str
    empresa: str
    equipo: str
    estado: RentaEstado
    total: Money
    pagado: Money
    saldo: Money


class CobranzaResumen(BaseModel):
    total_cotizado: Money
    total_pagado: Money
    saldo: Money
    pagos_por_confirmar: int


class CobranzaOut(BaseModel):
    items: list[CobranzaItem]
    total: int
    resumen: CobranzaResumen

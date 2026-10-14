"""Importar aquí todos los modelos para que Alembic los registre en Base.metadata."""

from app.models.bloqueo import Bloqueo, BloqueoEstado, BloqueoTipo
from app.models.categoria import Categoria
from app.models.cotizacion import (
    Cotizacion,
    CotizacionEstado,
    CotizacionPartida,
    PartidaConcepto,
    PartidaUnidad,
)
from app.models.cumplimiento import Pago, RentaDocumento, RevisionEstado
from app.models.empresa import Empresa, EmpresaStatus
from app.models.equipo import Equipo, EquipoFoto, EquipoStatus
from app.models.movimiento import MovimientoTipo, RentaMovimiento
from app.models.renta import OperadorModo, Renta, RentaEstado, Transporte
from app.models.user import Role, User

__all__ = [
    "Bloqueo",
    "BloqueoEstado",
    "BloqueoTipo",
    "Categoria",
    "Cotizacion",
    "CotizacionEstado",
    "CotizacionPartida",
    "Empresa",
    "EmpresaStatus",
    "Equipo",
    "EquipoFoto",
    "EquipoStatus",
    "MovimientoTipo",
    "OperadorModo",
    "Pago",
    "PartidaConcepto",
    "PartidaUnidad",
    "Renta",
    "RentaDocumento",
    "RentaEstado",
    "RentaMovimiento",
    "RevisionEstado",
    "Role",
    "Transporte",
    "User",
]

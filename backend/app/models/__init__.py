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
from app.models.empresa import Empresa, EmpresaStatus
from app.models.equipo import Equipo, EquipoFoto, EquipoStatus
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
    "OperadorModo",
    "PartidaConcepto",
    "PartidaUnidad",
    "Renta",
    "RentaEstado",
    "Role",
    "Transporte",
    "User",
]

"""Importar aquí todos los modelos para que Alembic los registre en Base.metadata."""

from app.models.categoria import Categoria
from app.models.empresa import Empresa, EmpresaStatus
from app.models.equipo import Equipo, EquipoFoto, EquipoStatus
from app.models.user import Role, User

__all__ = [
    "Categoria",
    "Empresa",
    "EmpresaStatus",
    "Equipo",
    "EquipoFoto",
    "EquipoStatus",
    "Role",
    "User",
]

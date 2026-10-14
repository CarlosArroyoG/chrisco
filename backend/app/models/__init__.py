"""Importar aquí todos los modelos para que Alembic los registre en Base.metadata."""

from app.models.empresa import Empresa, EmpresaStatus
from app.models.user import Role, User

__all__ = ["Empresa", "EmpresaStatus", "Role", "User"]

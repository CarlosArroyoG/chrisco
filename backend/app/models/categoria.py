from typing import TYPE_CHECKING, Any

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.equipo import Equipo


class Categoria(IdMixin, TimestampMixin, Base):
    """Tipo de maquinaria. Define qué especificaciones se capturan para sus equipos."""

    __tablename__ = "categorias"

    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    # Lista de campos (ver `app.schemas.equipo.SpecField`). Permite tipos nuevos sin cambiar código.
    spec_fields: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )

    equipos: Mapped[list["Equipo"]] = relationship(back_populates="categoria")

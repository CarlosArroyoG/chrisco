import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import false

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.categoria import Categoria


class EquipoStatus(enum.StrEnum):
    """Estado administrativo. Si está rentado o bloqueado se calcula aparte (fases 4 y 6)."""

    ACTIVO = "activo"
    MANTENIMIENTO = "mantenimiento"
    BAJA = "baja"


class Equipo(IdMixin, TimestampMixin, Base):
    __tablename__ = "equipos"
    __table_args__ = (
        CheckConstraint(
            "tarifa_hora IS NOT NULL OR tarifa_dia IS NOT NULL", name="tarifa_requerida"
        ),
        CheckConstraint(
            "coalesce(tarifa_hora, 1) > 0 AND coalesce(tarifa_dia, 1) > 0", name="tarifas_positivas"
        ),
        CheckConstraint("horometro >= 0", name="horometro_no_negativo"),
        CheckConstraint("anio IS NULL OR anio BETWEEN 1950 AND 2100", name="anio_valido"),
    )

    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    categoria_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("categorias.id", ondelete="RESTRICT"), index=True
    )
    nombre: Mapped[str] = mapped_column(String(120))
    marca: Mapped[str] = mapped_column(String(60))
    modelo: Mapped[str] = mapped_column(String(80))
    numero_serie: Mapped[str] = mapped_column(String(60), unique=True)
    anio: Mapped[int | None] = mapped_column(SmallInteger)
    horometro: Mapped[Decimal] = mapped_column(Numeric(10, 1), default=Decimal(0))
    patio: Mapped[str] = mapped_column(String(80))
    tarifa_hora: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    tarifa_dia: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    # Requisitos que el sistema usa al armar una solicitud (fase 5).
    requiere_lowboy: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    requiere_operador_certificado: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    status: Mapped[EquipoStatus] = mapped_column(
        Enum(EquipoStatus, name="equipo_status", values_callable=lambda e: [m.value for m in e]),
        default=EquipoStatus.ACTIVO,
    )
    specs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    notas: Mapped[str | None] = mapped_column(Text)

    categoria: Mapped["Categoria"] = relationship(back_populates="equipos")

    @property
    def categoria_nombre(self) -> str:
        return self.categoria.nombre

    fotos: Mapped[list["EquipoFoto"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan", order_by="EquipoFoto.position"
    )


class EquipoFoto(IdMixin, TimestampMixin, Base):
    """Foto de un equipo. La primera (posición más baja) es la portada del catálogo."""

    __tablename__ = "equipo_fotos"

    equipo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipos.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(100))
    thumb_key: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(Integer, default=0)

    equipo: Mapped[Equipo] = relationship(back_populates="fotos")

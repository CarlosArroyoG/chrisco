import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.renta import Renta
    from app.models.user import User


class MovimientoTipo(enum.StrEnum):
    SALIDA = "salida"  # el equipo sale del patio hacia la obra (check-in de la renta)
    REGRESO = "regreso"  # el equipo vuelve al patio (check-out)


class RentaMovimiento(IdMixin, TimestampMixin, Base):
    """Salida o regreso de un equipo, con la lectura del horómetro y una foto del tablero."""

    __tablename__ = "renta_movimientos"
    __table_args__ = (
        UniqueConstraint("renta_id", "tipo", name="un_movimiento_por_tipo"),
        CheckConstraint("horometro >= 0", name="horometro_no_negativo"),
    )

    renta_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rentas.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[MovimientoTipo] = mapped_column(
        Enum(MovimientoTipo, name="movimiento_tipo", values_callable=lambda e: [m.value for m in e])
    )
    horometro: Mapped[Decimal] = mapped_column(Numeric(10, 1))
    foto_key: Mapped[str] = mapped_column(String(100))  # almacenamiento privado
    notas: Mapped[str | None] = mapped_column(Text)
    registrado_por_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )

    renta: Mapped["Renta"] = relationship(back_populates="movimientos")
    registrado_por: Mapped["User"] = relationship()

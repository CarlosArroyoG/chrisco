import enum
import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.equipo import Equipo
    from app.models.user import User


class GastoCategoria(enum.StrEnum):
    MANTENIMIENTO = "mantenimiento"
    REFACCIONES = "refacciones"
    COMBUSTIBLE = "combustible"
    OPERADOR = "operador"
    FLETE = "flete"
    OTRO = "otro"


class Gasto(IdMixin, TimestampMixin, Base):
    """Dinero que sale del negocio. Junto con lo cobrado da la ganancia del mes."""

    __tablename__ = "gastos"
    __table_args__ = (CheckConstraint("monto > 0", name="monto_positivo"),)

    fecha: Mapped[date] = mapped_column(Date, index=True)
    categoria: Mapped[GastoCategoria] = mapped_column(
        Enum(GastoCategoria, name="gasto_categoria", values_callable=lambda e: [m.value for m in e])
    )
    concepto: Mapped[str] = mapped_column(String(120))
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Equipo al que se atribuye (opcional); si el equipo se borra, el gasto se conserva.
    equipo_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("equipos.id", ondelete="SET NULL"), index=True
    )
    registrado_por_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )

    equipo: Mapped["Equipo | None"] = relationship()
    registrado_por: Mapped["User"] = relationship()

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.renta import Renta
    from app.models.user import User


class RevisionEstado(enum.StrEnum):
    """Estado de algo que el cliente entrega y el personal revisa (documento o pago)."""

    PENDIENTE = "pendiente"  # entregado, esperando revisión
    APROBADO = "aprobado"  # documento aprobado / pago confirmado
    RECHAZADO = "rechazado"


class RentaDocumento(IdMixin, TimestampMixin, Base):
    """Archivo que el cliente sube para cumplir un requisito (contrato, póliza, licencia…)."""

    __tablename__ = "renta_documentos"

    renta_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rentas.id", ondelete="CASCADE"), index=True
    )
    requisito: Mapped[str] = mapped_column(String(40))  # código del requisito
    filename: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(100))  # archivo en almacenamiento privado
    estado: Mapped[RevisionEstado] = mapped_column(
        Enum(
            RevisionEstado, name="revision_estado", values_callable=lambda e: [m.value for m in e]
        ),
        default=RevisionEstado.PENDIENTE,
    )
    nota_revision: Mapped[str | None] = mapped_column(Text)
    subido_por_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    revisado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    revisado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Solo licencias: lo que el personal lee de la foto al aprobarla.
    numero: Mapped[str | None] = mapped_column(String(40))
    vigente_hasta: Mapped[date | None] = mapped_column(Date)

    renta: Mapped["Renta"] = relationship(back_populates="documentos")
    subido_por: Mapped["User"] = relationship(foreign_keys=[subido_por_id])


class Pago(IdMixin, TimestampMixin, Base):
    """Pago por transferencia que reporta el cliente con su comprobante; el personal lo confirma."""

    __tablename__ = "pagos"
    __table_args__ = (CheckConstraint("monto > 0", name="monto_positivo"),)

    renta_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rentas.id", ondelete="CASCADE"), index=True
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    fecha_pago: Mapped[date] = mapped_column(Date)
    referencia: Mapped[str | None] = mapped_column(String(60))  # clave de rastreo
    comprobante_key: Mapped[str] = mapped_column(String(100))
    estado: Mapped[RevisionEstado] = mapped_column(
        Enum(
            RevisionEstado, name="revision_estado", values_callable=lambda e: [m.value for m in e]
        ),
        default=RevisionEstado.PENDIENTE,
    )
    nota_revision: Mapped[str | None] = mapped_column(Text)
    reportado_por_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    revisado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    revisado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    renta: Mapped["Renta"] = relationship(back_populates="pagos")
    reportado_por: Mapped["User"] = relationship(foreign_keys=[reportado_por_id])

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.renta import Renta
    from app.models.user import User


class CotizacionEstado(enum.StrEnum):
    VIGENTE = "vigente"  # enviada al cliente, esperando respuesta
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    REEMPLAZADA = "reemplazada"  # ventas envió una versión nueva
    VENCIDA = "vencida"  # pasó su vigencia sin respuesta


class PartidaConcepto(enum.StrEnum):
    RENTA = "renta"
    FLETE = "flete"  # traslado en lowboy u otro
    TRAILER = "trailer"  # tractocamión adicional
    COMBUSTIBLE = "combustible"
    OPERADOR = "operador"
    SEGURO = "seguro"
    OTRO = "otro"


class PartidaUnidad(enum.StrEnum):
    HORA = "hora"
    DIA = "dia"
    VIAJE = "viaje"
    LITRO = "litro"
    SERVICIO = "servicio"


class Cotizacion(IdMixin, TimestampMixin, Base):
    __tablename__ = "cotizaciones"
    __table_args__ = (
        # Una renta tiene a lo mucho una cotización viva (vigente o ya aceptada).
        Index(
            "uq_cotizaciones_viva_por_renta",
            "renta_id",
            unique=True,
            postgresql_where=text("estado IN ('vigente', 'aceptada')"),
        ),
        CheckConstraint("total = subtotal + iva", name="total_cuadra"),
        CheckConstraint("anticipo_monto >= 0 AND anticipo_monto <= total", name="anticipo_valido"),
    )

    renta_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rentas.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    estado: Mapped[CotizacionEstado] = mapped_column(
        Enum(
            CotizacionEstado,
            name="cotizacion_estado",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=CotizacionEstado.VIGENTE,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    iva: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    anticipo_monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valida_hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notas: Mapped[str | None] = mapped_column(Text)
    creada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    renta: Mapped["Renta"] = relationship(back_populates="cotizaciones")
    creada_por: Mapped["User | None"] = relationship()
    partidas: Mapped[list["CotizacionPartida"]] = relationship(
        back_populates="cotizacion",
        cascade="all, delete-orphan",
        order_by="CotizacionPartida.orden",
    )


class CotizacionPartida(IdMixin, Base):
    __tablename__ = "cotizacion_partidas"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="precio_no_negativo"),
    )

    cotizacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cotizaciones.id", ondelete="CASCADE"), index=True
    )
    orden: Mapped[int] = mapped_column(Integer)
    concepto: Mapped[PartidaConcepto] = mapped_column(
        Enum(
            PartidaConcepto, name="partida_concepto", values_callable=lambda e: [m.value for m in e]
        )
    )
    descripcion: Mapped[str] = mapped_column(String(200))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unidad: Mapped[PartidaUnidad] = mapped_column(
        Enum(PartidaUnidad, name="partida_unidad", values_callable=lambda e: [m.value for m in e])
    )
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    importe: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    cotizacion: Mapped[Cotizacion] = relationship(back_populates="partidas")

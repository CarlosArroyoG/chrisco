import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Sequence,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.bloqueo import Bloqueo
    from app.models.empresa import Empresa
    from app.models.equipo import Equipo
    from app.models.user import User

# Numeración de folios (CHR-2026-00001). Una secuencia no se salta ni repite aunque haya
# solicitudes simultáneas.
renta_folio_seq = Sequence("renta_folio_seq", metadata=Base.metadata)


class RentaEstado(enum.StrEnum):
    """Ciclo de vida de una renta. Las fases 5 y 6 recorren estos estados en orden."""

    SOLICITADA = "solicitada"  # el cliente pidió el equipo; reservado 20 min
    COTIZADA = "cotizada"  # ventas envió la cotización
    APARTADA = "apartada"  # el cliente aceptó; 3 h para cumplir requisitos y pagar el anticipo
    CONFIRMADA = "confirmada"  # requisitos cumplidos y anticipo recibido
    EN_RENTA = "en_renta"  # el equipo salió (check-in)
    DEVUELTA = "devuelta"  # regresó (check-out)
    CERRADA = "cerrada"  # cobrada por completo
    VENCIDA = "vencida"  # la reserva provisional caducó sin avanzar
    CANCELADA = "cancelada"
    RECHAZADA = "rechazada"  # ventas no pudo atenderla


class OperadorModo(enum.StrEnum):
    CHRISCO = "chrisco"  # opera personal de CHRISCO
    CLIENTE = "cliente"  # opera un chofer de la empresa cliente (exige licencia verificada)


class Transporte(enum.StrEnum):
    ENTREGA = "entrega"  # CHRISCO lleva el equipo al sitio
    RECOGE = "recoge"  # el cliente lo recoge en el patio


class Renta(IdMixin, TimestampMixin, Base):
    __tablename__ = "rentas"
    __table_args__ = (CheckConstraint("hasta > desde", name="periodo_valido"),)

    folio: Mapped[str] = mapped_column(String(20), unique=True)
    estado: Mapped[RentaEstado] = mapped_column(
        Enum(RentaEstado, name="renta_estado", values_callable=lambda e: [m.value for m in e]),
        default=RentaEstado.SOLICITADA,
        index=True,
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("empresas.id", ondelete="RESTRICT"), index=True
    )
    solicitante_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    equipo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipos.id", ondelete="RESTRICT"), index=True
    )
    # Bloqueo que reserva el equipo; su estado y vencimiento mandan sobre el de la solicitud.
    bloqueo_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("bloqueos.id", ondelete="RESTRICT"), unique=True
    )
    desde: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    destino: Mapped[str] = mapped_column(String(200))
    operador_modo: Mapped[OperadorModo] = mapped_column(
        Enum(OperadorModo, name="operador_modo", values_callable=lambda e: [m.value for m in e])
    )
    transporte: Mapped[Transporte] = mapped_column(
        Enum(Transporte, name="transporte", values_callable=lambda e: [m.value for m in e])
    )
    notas: Mapped[str | None] = mapped_column(Text)
    # Los requisitos se guardan tal como se mostraron: cambiar las reglas no reescribe la historia.
    requisitos: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )

    empresa: Mapped["Empresa"] = relationship()
    solicitante: Mapped["User"] = relationship()
    equipo: Mapped["Equipo"] = relationship()
    bloqueo: Mapped["Bloqueo | None"] = relationship()

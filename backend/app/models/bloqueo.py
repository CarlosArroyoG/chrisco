import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Uuid, text
from sqlalchemy.dialects.postgresql import TSTZRANGE, ExcludeConstraint, Range
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.equipo import Equipo
    from app.models.user import User


class BloqueoTipo(enum.StrEnum):
    SOLICITUD = "solicitud"  # reserva provisional mientras ventas cotiza (20 min)
    APARTADO = "apartado"  # cotización aceptada; espera requisitos y anticipo (3 h)
    RENTA = "renta"  # renta confirmada: no vence
    MANTENIMIENTO = "mantenimiento"  # ventana de servicio programada
    MANUAL = "manual"  # el personal aparta el equipo por otra razón


class BloqueoEstado(enum.StrEnum):
    ACTIVO = "activo"
    LIBERADO = "liberado"  # se canceló o terminó
    EXPIRADO = "expirado"  # una reserva provisional venció sin confirmarse


# Los bloqueos provisionales caducan; el resto no.
HOLD_TYPES = (BloqueoTipo.SOLICITUD, BloqueoTipo.APARTADO)


class Bloqueo(IdMixin, TimestampMixin, Base):
    """Periodo en el que un equipo no está disponible.

    La restricción de exclusión impide que dos bloqueos activos del mismo equipo se traslapen:
    es la garantía de que no hay dobles reservas, aunque dos usuarios actúen a la vez.
    """

    __tablename__ = "bloqueos"
    __table_args__ = (
        ExcludeConstraint(
            ("equipo_id", "="),
            ("periodo", "&&"),
            using="gist",
            where=text("estado = 'activo'"),
            name="ex_bloqueos_sin_traslape",
        ),
        CheckConstraint("NOT isempty(periodo)", name="periodo_no_vacio"),
        # Solo las reservas provisionales llevan fecha de vencimiento (y todas la llevan).
        CheckConstraint(
            "(tipo IN ('solicitud', 'apartado')) = (vence_en IS NOT NULL)", name="vence_solo_holds"
        ),
        CheckConstraint(
            "tipo NOT IN ('mantenimiento', 'manual') OR motivo IS NOT NULL", name="motivo_requerido"
        ),
    )

    equipo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipos.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[BloqueoTipo] = mapped_column(
        Enum(BloqueoTipo, name="bloqueo_tipo", values_callable=lambda e: [m.value for m in e])
    )
    estado: Mapped[BloqueoEstado] = mapped_column(
        Enum(BloqueoEstado, name="bloqueo_estado", values_callable=lambda e: [m.value for m in e]),
        default=BloqueoEstado.ACTIVO,
    )
    # [desde, hasta): el equipo vuelve a estar libre justo en `hasta`.
    periodo: Mapped[Range[datetime]] = mapped_column(TSTZRANGE)
    vence_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo: Mapped[str | None] = mapped_column(String(300))
    creado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    equipo: Mapped["Equipo"] = relationship()
    creado_por: Mapped["User | None"] = relationship()

    @property
    def desde(self) -> datetime:
        assert self.periodo.lower is not None
        return self.periodo.lower

    @property
    def hasta(self) -> datetime:
        assert self.periodo.upper is not None
        return self.periodo.upper

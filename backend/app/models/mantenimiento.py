import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import true

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.equipo import Equipo
    from app.models.user import User


class MantenimientoPlan(IdMixin, TimestampMixin, Base):
    """Un servicio periódico de un equipo (cambio de aceite, engrasado…): cada X horas y/o días."""

    __tablename__ = "mantenimiento_planes"
    __table_args__ = (
        UniqueConstraint("equipo_id", "nombre", name="un_plan_por_nombre"),
        CheckConstraint("cada_horas IS NOT NULL OR cada_dias IS NOT NULL", name="intervalo"),
        CheckConstraint(
            "coalesce(cada_horas, 1) > 0 AND coalesce(cada_dias, 1) > 0", name="positivo"
        ),
    )

    equipo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipos.id", ondelete="CASCADE"), index=True
    )
    nombre: Mapped[str] = mapped_column(String(80))
    cada_horas: Mapped[Decimal | None] = mapped_column(Numeric(10, 1))
    cada_dias: Mapped[int | None] = mapped_column(Integer)
    # Cuándo y con qué horómetro se hizo la última vez (o se dio de alta el plan).
    ultimo_horometro: Mapped[Decimal] = mapped_column(Numeric(10, 1))
    ultima_fecha: Mapped[date] = mapped_column(Date)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Última alerta enviada ("proximo" o "vencido"): evita repetir el mismo aviso cada día.
    alerta_enviada: Mapped[str | None] = mapped_column(String(10))

    equipo: Mapped["Equipo"] = relationship()
    registros: Mapped[list["MantenimientoRegistro"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="MantenimientoRegistro.fecha"
    )


class MantenimientoRegistro(IdMixin, TimestampMixin, Base):
    """Una vez que se hizo el servicio."""

    __tablename__ = "mantenimiento_registros"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("mantenimiento_planes.id", ondelete="CASCADE"), index=True
    )
    fecha: Mapped[date] = mapped_column(Date)
    horometro: Mapped[Decimal] = mapped_column(Numeric(10, 1))
    notas: Mapped[str | None] = mapped_column(Text)
    registrado_por_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )

    plan: Mapped[MantenimientoPlan] = relationship(back_populates="registros")
    registrado_por: Mapped["User"] = relationship()

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class EmpresaStatus(enum.StrEnum):
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"


class Empresa(IdMixin, TimestampMixin, Base):
    """Empresa cliente. Solo una empresa aprobada puede solicitar equipo."""

    __tablename__ = "empresas"

    razon_social: Mapped[str] = mapped_column(String(200))
    sitio_web: Mapped[str] = mapped_column(String(255))
    rfc: Mapped[str] = mapped_column(String(13), unique=True, index=True)
    status: Mapped[EmpresaStatus] = mapped_column(
        Enum(EmpresaStatus, name="empresa_status", values_callable=lambda e: [m.value for m in e]),
        default=EmpresaStatus.PENDIENTE,
    )
    motivo_rechazo: Mapped[str | None] = mapped_column(Text)
    # Clave del archivo en el almacenamiento privado (constancia de situación fiscal, PDF).
    constancia_key: Mapped[str] = mapped_column(String(100))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", use_alter=True)
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    users: Mapped[list["User"]] = relationship(
        back_populates="empresa", foreign_keys="User.empresa_id", order_by="User.created_at"
    )
    reviewed_by: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by_id])

    @property
    def owner(self) -> "User | None":
        return next((u for u in self.users if u.is_company_owner), None)

    @property
    def active_users(self) -> int:
        return sum(1 for u in self.users if u.is_active)

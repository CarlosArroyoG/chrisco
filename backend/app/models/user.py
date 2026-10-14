import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import false

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.empresa import Empresa


class Role(enum.StrEnum):
    ADMIN = "admin"
    VENTAS = "ventas"
    OPERADOR = "operador"
    CLIENTE = "cliente"


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # Un usuario es cliente si y solo si pertenece a una empresa.
        CheckConstraint(
            "(role = 'cliente') = (empresa_id IS NOT NULL)", name="cliente_tiene_empresa"
        ),
    )

    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="role", values_callable=lambda r: [m.value for m in r])
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Se incrementa para invalidar todos los tokens emitidos (cierre de sesión global).
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    # None mientras no confirme su correo (o no acepte su invitación): no puede iniciar sesión.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("empresas.id", ondelete="RESTRICT")
    )
    # Titular de la empresa: el primero en registrarse; puede invitar a los demás usuarios.
    is_company_owner: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    empresa: Mapped["Empresa | None"] = relationship(
        back_populates="users", foreign_keys=[empresa_id]
    )

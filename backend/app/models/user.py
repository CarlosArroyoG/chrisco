import enum

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Role(enum.StrEnum):
    ADMIN = "admin"
    VENTAS = "ventas"
    OPERADOR = "operador"
    CLIENTE = "cliente"


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="role", values_callable=lambda r: [m.value for m in r])
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Se incrementa para invalidar todos los tokens emitidos (cierre de sesión global).
    token_version: Mapped[int] = mapped_column(Integer, default=0)

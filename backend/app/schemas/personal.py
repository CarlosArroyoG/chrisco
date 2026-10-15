import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Los clientes no se dan de alta aquí: se registran solos con su empresa.
StaffRole = Literal["admin", "ventas", "operador"]


class PersonalIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    role: StaffRole


class PersonalUpdate(BaseModel):
    """Cambia el rol y/o activa o desactiva a una persona del personal."""

    role: StaffRole | None = None
    is_active: bool | None = None


class PersonalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: StaffRole
    is_active: bool
    # True mientras no haya creado su contraseña con el enlace de la invitación.
    pendiente_invitacion: bool
    created_at: datetime

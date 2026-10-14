import re
import uuid
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
)

from app.core.config import get_settings
from app.core.rfc import normalize_rfc
from app.models.empresa import Empresa, EmpresaStatus
from app.schemas.auth import Password

_http_url = TypeAdapter(HttpUrl)


class CompanyData(BaseModel):
    """Datos fiscales de la empresa. Los comparten el registro y el reenvío tras un rechazo."""

    model_config = ConfigDict(str_strip_whitespace=True)

    razon_social: str = Field(min_length=2, max_length=200)
    sitio_web: str = Field(min_length=3, max_length=255)
    rfc: str

    @field_validator("rfc")
    @classmethod
    def _rfc(cls, value: str) -> str:
        return normalize_rfc(value)

    @field_validator("sitio_web")
    @classmethod
    def _web(cls, value: str) -> str:
        if not re.match(r"^https?://", value, re.IGNORECASE):
            value = f"https://{value}"
        return str(_http_url.validate_python(value))


class RegistroEmpresaForm(CompanyData):
    """Alta de empresa + su primer usuario (el titular). Llega como multipart con la constancia."""

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: Password


class InviteUserRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)


class RejectRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    motivo: str = Field(min_length=5, max_length=500)


class CompanyUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_company_owner: bool
    is_active: bool
    email_verified_at: datetime | None


class EmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    razon_social: str
    sitio_web: str
    rfc: str
    status: EmpresaStatus
    motivo_rechazo: str | None
    created_at: datetime
    reviewed_at: datetime | None


class EmpresaDetailOut(EmpresaOut):
    users: list[CompanyUserOut]
    max_users: int


class EmpresaListItem(EmpresaOut):
    owner_name: str | None
    owner_email: EmailStr | None
    active_users: int

    @classmethod
    def from_empresa(cls, empresa: Empresa) -> "EmpresaListItem":
        owner = empresa.owner
        return cls(
            **EmpresaOut.model_validate(empresa).model_dump(),
            owner_name=owner.full_name if owner else None,
            owner_email=owner.email if owner else None,
            active_users=empresa.active_users,
        )


def empresa_detail(empresa: Empresa) -> EmpresaDetailOut:
    return EmpresaDetailOut(
        **EmpresaOut.model_validate(empresa).model_dump(),
        users=[CompanyUserOut.model_validate(u) for u in empresa.users],
        max_users=get_settings().max_users_per_company,
    )

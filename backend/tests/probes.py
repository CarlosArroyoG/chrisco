"""Rutas solo para pruebas: ejercitan las dependencias de acceso."""

from fastapi import APIRouter, Depends

from app.api.deps import ApprovedClientUser, CompanyOwner, require_roles
from app.models.user import Role

probe_router = APIRouter(prefix="/_probe")


@probe_router.get("/admin-only", dependencies=[Depends(require_roles(Role.ADMIN))])
def admin_only() -> dict[str, bool]:
    return {"ok": True}


@probe_router.get("/approved-client")
def approved_client(_: ApprovedClientUser) -> dict[str, bool]:
    return {"ok": True}


@probe_router.get("/company-owner")
def company_owner(_: CompanyOwner) -> dict[str, bool]:
    return {"ok": True}

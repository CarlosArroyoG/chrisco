"""Panel del administrador: cifras del mes, gráficas y lo que requiere atención."""

from fastapi import APIRouter

from app.api.deps import DbSession, StaffUser
from app.schemas.dashboard import DashboardOut
from app.services import dashboard

router = APIRouter(prefix="/admin/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(_: StaffUser, db: DbSession) -> DashboardOut:
    return dashboard.summary(db)

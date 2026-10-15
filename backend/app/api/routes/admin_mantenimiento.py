"""Planes de mantenimiento periódico de los equipos (ver: admin y ventas; cambiar: admin)."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, DbSession, StaffUser
from app.schemas.mantenimiento import (
    AtencionItem,
    PlanIn,
    PlanOut,
    RealizadoIn,
    RegistroOut,
)
from app.services import equipos, mantenimiento

router = APIRouter(tags=["mantenimiento"])


@router.get("/admin/mantenimiento", response_model=list[AtencionItem])
def attention(_: StaffUser, db: DbSession, solo_atencion: bool = False) -> list[AtencionItem]:
    """Planes de todos los equipos, los más urgentes primero."""
    return mantenimiento.attention(db, only_due=solo_atencion)


@router.get("/admin/equipos/{equipo_id}/mantenimiento", response_model=list[PlanOut])
def list_planes(_: StaffUser, equipo_id: uuid.UUID, db: DbSession) -> list[PlanOut]:
    equipos.get_equipo(db, equipo_id)
    return [mantenimiento.plan_out(p) for p in mantenimiento.list_for_equipo(db, equipo_id)]


@router.post(
    "/admin/equipos/{equipo_id}/mantenimiento",
    response_model=PlanOut,
    status_code=status.HTTP_201_CREATED,
)
def create_plan(_: AdminUser, equipo_id: uuid.UUID, body: PlanIn, db: DbSession) -> PlanOut:
    equipo = equipos.get_equipo(db, equipo_id)
    return mantenimiento.plan_out(mantenimiento.create_plan(db, equipo, body))


@router.put("/admin/mantenimiento/{plan_id}", response_model=PlanOut)
def update_plan(_: AdminUser, plan_id: uuid.UUID, body: PlanIn, db: DbSession) -> PlanOut:
    plan = mantenimiento.get_plan(db, plan_id)
    return mantenimiento.plan_out(mantenimiento.update_plan(db, plan, body))


@router.delete("/admin/mantenimiento/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(_: AdminUser, plan_id: uuid.UUID, db: DbSession) -> None:
    mantenimiento.delete_plan(db, mantenimiento.get_plan(db, plan_id))


@router.post(
    "/admin/mantenimiento/{plan_id}/realizado",
    response_model=RegistroOut,
    status_code=status.HTTP_201_CREATED,
)
def register_done(
    admin: AdminUser, plan_id: uuid.UUID, body: RealizadoIn, db: DbSession
) -> RegistroOut:
    plan = mantenimiento.get_plan(db, plan_id)
    return mantenimiento.registro_out(mantenimiento.register_done(db, plan, admin, body))


@router.get("/admin/mantenimiento/{plan_id}/registros", response_model=list[RegistroOut])
def list_registros(_: StaffUser, plan_id: uuid.UUID, db: DbSession) -> list[RegistroOut]:
    plan = mantenimiento.get_plan(db, plan_id)
    return [mantenimiento.registro_out(r) for r in reversed(plan.registros)]

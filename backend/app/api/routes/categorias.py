"""Categorías de maquinaria: lectura para quien ve el catálogo; gestión para el personal."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, CatalogUser, DbSession, StaffUser
from app.schemas.equipo import CategoriaAdminOut, CategoriaIn, CategoriaOut
from app.services import categorias

router = APIRouter(tags=["categorias"])


@router.get("/categorias", response_model=list[CategoriaOut])
def list_categorias(_: CatalogUser, db: DbSession) -> list[CategoriaOut]:
    return [CategoriaOut.model_validate(c) for c in categorias.list_categorias(db)]


@router.get("/admin/categorias", response_model=list[CategoriaAdminOut])
def list_categorias_admin(_: StaffUser, db: DbSession) -> list[CategoriaAdminOut]:
    return categorias.list_with_counts(db)


@router.post("/admin/categorias", response_model=CategoriaOut, status_code=status.HTTP_201_CREATED)
def create_categoria(_: AdminUser, body: CategoriaIn, db: DbSession) -> CategoriaOut:
    return CategoriaOut.model_validate(categorias.create(db, body))


@router.put("/admin/categorias/{categoria_id}", response_model=CategoriaOut)
def update_categoria(
    _: AdminUser, categoria_id: uuid.UUID, body: CategoriaIn, db: DbSession
) -> CategoriaOut:
    categoria = categorias.get_categoria(db, categoria_id)
    return CategoriaOut.model_validate(categorias.update(db, categoria, body))


@router.delete("/admin/categorias/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_categoria(_: AdminUser, categoria_id: uuid.UUID, db: DbSession) -> None:
    categorias.delete(db, categorias.get_categoria(db, categoria_id))

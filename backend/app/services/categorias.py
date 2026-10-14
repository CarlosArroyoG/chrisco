"""Categorías de maquinaria y las especificaciones que piden a sus equipos."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound
from app.models.categoria import Categoria
from app.models.equipo import Equipo
from app.schemas.equipo import CategoriaAdminOut, CategoriaIn, CategoriaOut

_NAME_TAKEN = "Ya existe una categoría con ese nombre"


def get_categoria(db: Session, categoria_id: uuid.UUID) -> Categoria:
    categoria = db.get(Categoria, categoria_id)
    if categoria is None:
        raise NotFound("Categoría no encontrada")
    return categoria


def list_categorias(db: Session) -> list[Categoria]:
    return list(db.scalars(select(Categoria).order_by(Categoria.nombre)))


def list_with_counts(db: Session) -> list[CategoriaAdminOut]:
    counts = {
        categoria_id: total
        for categoria_id, total in db.execute(
            select(Equipo.categoria_id, func.count()).group_by(Equipo.categoria_id)
        )
    }
    return [
        CategoriaAdminOut(
            **CategoriaOut.model_validate(c).model_dump(), equipos_count=counts.get(c.id, 0)
        )
        for c in list_categorias(db)
    ]


def _name_taken(db: Session, nombre: str, own_id: uuid.UUID | None = None) -> bool:
    query = select(Categoria.id).where(func.lower(Categoria.nombre) == nombre.lower())
    if own_id:
        query = query.where(Categoria.id != own_id)
    return db.scalar(query) is not None


def _save(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict(_NAME_TAKEN) from None


def create(db: Session, data: CategoriaIn) -> Categoria:
    if _name_taken(db, data.nombre):
        raise Conflict(_NAME_TAKEN)
    categoria = Categoria(
        nombre=data.nombre, spec_fields=[f.model_dump(mode="json") for f in data.spec_fields]
    )
    db.add(categoria)
    _save(db)
    return categoria


def update(db: Session, categoria: Categoria, data: CategoriaIn) -> Categoria:
    """Cambiar los campos no reescribe los equipos ya guardados; solo rige para ediciones nuevas."""
    if _name_taken(db, data.nombre, categoria.id):
        raise Conflict(_NAME_TAKEN)
    categoria.nombre = data.nombre
    categoria.spec_fields = [f.model_dump(mode="json") for f in data.spec_fields]
    _save(db)
    return categoria


def delete(db: Session, categoria: Categoria) -> None:
    in_use = db.scalar(
        select(func.count()).select_from(Equipo).where(Equipo.categoria_id == categoria.id)
    )
    if in_use:
        raise Conflict(f"No se puede eliminar: la categoría tiene {in_use} equipo(s)")
    db.delete(categoria)
    db.commit()

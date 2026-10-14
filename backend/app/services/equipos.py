"""Registro de equipos: alta, edición, búsqueda y fotos."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import Conflict, NotFound
from app.models.equipo import Equipo, EquipoFoto, EquipoStatus
from app.schemas.equipo import EquipoCatalogOut, EquipoIn, EquipoOut, EquipoUpdate, FotoOut
from app.services import categorias, disponibilidad, images, specs
from app.services.storage import PrivateStorage

MAX_PHOTOS = 10
_DUPLICATE = "Ya existe un equipo con ese código o número de serie"

# Campos del esquema que se copian tal cual al modelo.
_FIELDS = tuple(f for f in EquipoIn.model_fields if f != "specs")


def get_equipo(db: Session, equipo_id: uuid.UUID) -> Equipo:
    equipo = db.get(Equipo, equipo_id)
    if equipo is None:
        raise NotFound("Equipo no encontrado")
    return equipo


def get_active_equipo(db: Session, equipo_id: uuid.UUID) -> Equipo:
    """Equipo visible para clientes (activo); si no, «no existe»."""
    equipo = get_equipo(db, equipo_id)
    if equipo.status != EquipoStatus.ACTIVO:
        raise NotFound("Equipo no encontrado")
    return equipo


def _check_unique(db: Session, codigo: str, serie: str, own_id: uuid.UUID | None = None) -> None:
    for column, value, label in (
        (Equipo.codigo, codigo, "código"),
        (Equipo.numero_serie, serie, "número de serie"),
    ):
        query = select(Equipo.id).where(column == value)
        if own_id:
            query = query.where(Equipo.id != own_id)
        if db.scalar(query):
            raise Conflict(f"Ya existe un equipo con ese {label}")


def apply_data(db: Session, equipo: Equipo, data: EquipoIn) -> None:
    """Copia los datos al equipo validando categoría y especificaciones."""
    categoria = categorias.get_categoria(db, data.categoria_id)
    equipo.specs = specs.validate_specs(specs.parse_fields(categoria.spec_fields), data.specs)
    for field in _FIELDS:
        setattr(equipo, field, getattr(data, field))


def commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:  # carrera entre dos altas con el mismo código o serie
        db.rollback()
        raise Conflict(_DUPLICATE) from None


def create(db: Session, data: EquipoIn) -> Equipo:
    _check_unique(db, data.codigo, data.numero_serie)
    equipo = Equipo()
    apply_data(db, equipo, data)
    db.add(equipo)
    commit(db)
    return equipo


def update(db: Session, equipo: Equipo, data: EquipoUpdate) -> Equipo:
    _check_unique(db, data.codigo, data.numero_serie, equipo.id)
    apply_data(db, equipo, data)
    equipo.status = data.status
    commit(db)
    return equipo


def search(
    db: Session,
    *,
    q: str | None = None,
    categoria_id: uuid.UUID | None = None,
    status: EquipoStatus | None = None,
    libre_entre: tuple[datetime, datetime] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Equipo], int]:
    query = select(Equipo)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                *(
                    c.ilike(like)
                    for c in (
                        Equipo.codigo,
                        Equipo.nombre,
                        Equipo.marca,
                        Equipo.modelo,
                        Equipo.numero_serie,
                    )
                )
            )
        )
    if categoria_id:
        query = query.where(Equipo.categoria_id == categoria_id)
    if libre_entre:
        query = query.where(disponibilidad.free_between(*libre_entre))
    if status:
        query = query.where(Equipo.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.options(selectinload(Equipo.fotos), selectinload(Equipo.categoria))
        .order_by(Equipo.codigo)
        .limit(limit)
        .offset(offset)
    )
    return list(items), total


def add_photo(db: Session, storage: PrivateStorage, equipo: Equipo, data: bytes) -> EquipoFoto:
    if len(equipo.fotos) >= MAX_PHOTOS:
        raise Conflict(f"Cada equipo admite hasta {MAX_PHOTOS} fotos")
    full, thumb = images.process_photo(data)
    key, thumb_key = storage.save_image(full, thumb)
    foto = EquipoFoto(
        key=key,
        thumb_key=thumb_key,
        position=max((f.position for f in equipo.fotos), default=-1) + 1,
    )
    equipo.fotos.append(foto)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key, thumb_key)
        raise
    return foto


def delete_photo(db: Session, storage: PrivateStorage, equipo: Equipo, foto_id: uuid.UUID) -> None:
    foto = next((f for f in equipo.fotos if f.id == foto_id), None)
    if foto is None:
        raise NotFound("Foto no encontrada")
    keys = (foto.key, foto.thumb_key)
    equipo.fotos.remove(foto)
    db.commit()
    storage.delete(*keys)


def get_photo(db: Session, foto_id: uuid.UUID) -> EquipoFoto:
    foto = db.get(EquipoFoto, foto_id)
    if foto is None:
        raise NotFound("Foto no encontrada")
    return foto


def to_out_many(db: Session, items: list[Equipo]) -> list[EquipoOut]:
    """Vista completa para el personal, con la situación actual de cada equipo."""
    estados = disponibilidad.estado_actual(db, items)
    return [
        EquipoOut.model_validate(
            {
                **{f: getattr(e, f) for f in EquipoOut.model_fields if f != "estado_actual"},
                "estado_actual": estados[e.id],
            },
            from_attributes=True,
        )
        for e in items
    ]


def to_out(db: Session, equipo: Equipo) -> EquipoOut:
    return to_out_many(db, [equipo])[0]


def catalog_out(equipo: Equipo, disponible: bool | None = None) -> EquipoCatalogOut:
    """Lo que ve un cliente: sin número de serie, horómetro ni notas internas."""
    shown: dict[str, Any] = {
        f: getattr(equipo, f)
        for f in (
            "id",
            "codigo",
            "nombre",
            "marca",
            "modelo",
            "anio",
            "categoria_id",
            "patio",
            "tarifa_hora",
            "tarifa_dia",
            "requiere_lowboy",
            "requiere_operador_certificado",
        )
    }
    return EquipoCatalogOut(
        **shown,
        categoria_nombre=equipo.categoria.nombre,
        specs=specs.display_specs(specs.parse_fields(equipo.categoria.spec_fields), equipo.specs),
        fotos=[FotoOut.model_validate(f) for f in equipo.fotos],
        disponible=disponible,
    )

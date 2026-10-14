"""Catálogo de maquinaria para clientes aprobados y personal. Las fotos son de acceso abierto."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pydantic import AwareDatetime

from app.api.deps import CatalogUser, DbSession, StorageDep
from app.core.errors import InvalidInput
from app.models.equipo import EquipoStatus
from app.schemas.common import Page
from app.schemas.disponibilidad import DisponibilidadOut
from app.schemas.equipo import EquipoCatalogOut
from app.services import disponibilidad, equipos

router = APIRouter(prefix="/equipos", tags=["catalogo"])


# Las fotos de los equipos son material de catálogo: se sirven sin sesión (sus ids son UUID) para
# que un <img> normal funcione, que no puede enviar encabezados de autorización.
@router.get("/fotos/{foto_id}/{size}", response_class=FileResponse)
def get_foto(
    foto_id: uuid.UUID, size: Literal["thumb", "full"], db: DbSession, storage: StorageDep
) -> FileResponse:
    foto = equipos.get_photo(db, foto_id)
    return FileResponse(
        storage.path(foto.thumb_key if size == "thumb" else foto.key),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@router.get("", response_model=Page[EquipoCatalogOut])
def list_catalogo(
    _: CatalogUser,
    db: DbSession,
    q: str | None = None,
    categoria_id: uuid.UUID | None = None,
    desde: AwareDatetime | None = None,
    hasta: AwareDatetime | None = None,
    solo_disponibles: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EquipoCatalogOut]:
    """Con `desde` y `hasta` cada equipo indica si está libre en ese periodo."""
    window = disponibilidad.parse_window(desde, hasta)
    if solo_disponibles and window is None:
        raise InvalidInput("Para ver solo los disponibles indica desde y hasta")
    items, total = equipos.search(
        db,
        q=q,
        categoria_id=categoria_id,
        status=EquipoStatus.ACTIVO,
        libre_entre=window if solo_disponibles else None,
        limit=limit,
        offset=offset,
    )
    busy = disponibilidad.occupied_ids(db, [e.id for e in items], *window) if window else set()
    return Page(
        items=[
            equipos.catalog_out(e, disponible=(e.id not in busy) if window else None) for e in items
        ],
        total=total,
    )


@router.get("/{equipo_id}", response_model=EquipoCatalogOut)
def get_catalogo(_: CatalogUser, equipo_id: uuid.UUID, db: DbSession) -> EquipoCatalogOut:
    return equipos.catalog_out(equipos.get_active_equipo(db, equipo_id))


@router.get("/{equipo_id}/disponibilidad", response_model=DisponibilidadOut)
def get_disponibilidad(
    _: CatalogUser,
    equipo_id: uuid.UUID,
    desde: AwareDatetime,
    hasta: AwareDatetime,
    db: DbSession,
) -> DisponibilidadOut:
    """Si el equipo está libre en el periodo y, si no, qué periodos tiene ocupados."""
    window = disponibilidad.parse_window(desde, hasta)
    assert window is not None
    equipo = equipos.get_active_equipo(db, equipo_id)
    ocupado = disponibilidad.occupations(db, equipo.id, *window)
    return DisponibilidadOut(disponible=not ocupado, desde=desde, hasta=hasta, ocupado=ocupado)

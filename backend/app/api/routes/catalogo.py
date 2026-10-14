"""Catálogo de maquinaria para clientes aprobados y personal. Las fotos son de acceso abierto."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.api.deps import CatalogUser, DbSession, StorageDep
from app.core.errors import NotFound
from app.models.equipo import EquipoStatus
from app.schemas.common import Page
from app.schemas.equipo import EquipoCatalogOut
from app.services import equipos

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
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EquipoCatalogOut]:
    items, total = equipos.search(
        db,
        q=q,
        categoria_id=categoria_id,
        status=EquipoStatus.ACTIVO,
        limit=limit,
        offset=offset,
    )
    return Page(items=[equipos.catalog_out(e) for e in items], total=total)


@router.get("/{equipo_id}", response_model=EquipoCatalogOut)
def get_catalogo(_: CatalogUser, equipo_id: uuid.UUID, db: DbSession) -> EquipoCatalogOut:
    equipo = equipos.get_equipo(db, equipo_id)
    if equipo.status != EquipoStatus.ACTIVO:
        raise NotFound("Equipo no encontrado")
    return equipos.catalog_out(equipo)

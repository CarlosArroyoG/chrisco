"""Registro de equipos. Ver: admin y ventas. Crear, editar, fotos e importar: solo admin."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.api.deps import AdminUser, DbSession, StaffUser, StorageDep
from app.models.equipo import EquipoStatus
from app.schemas.common import Page
from app.schemas.equipo import EquipoIn, EquipoOut, EquipoUpdate, FotoOut, ImportResult
from app.services import categorias, equipos, equipos_import
from app.services.storage import read_limited

router = APIRouter(prefix="/admin/equipos", tags=["equipos"])


@router.get("", response_model=Page[EquipoOut])
def list_equipos(
    _: StaffUser,
    db: DbSession,
    q: str | None = None,
    categoria_id: uuid.UUID | None = None,
    status_filter: EquipoStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EquipoOut]:
    items, total = equipos.search(
        db, q=q, categoria_id=categoria_id, status=status_filter, limit=limit, offset=offset
    )
    return Page(items=equipos.to_out_many(db, items), total=total)


@router.post("", response_model=EquipoOut, status_code=status.HTTP_201_CREATED)
def create_equipo(_: AdminUser, body: EquipoIn, db: DbSession) -> EquipoOut:
    return equipos.to_out(db, equipos.create(db, body))


# Las rutas fijas van antes que `/{equipo_id}` para que "importar" no se lea como un id.
@router.get("/importar/plantilla")
def import_template(_: StaffUser, db: DbSession, categoria_id: uuid.UUID | None = None) -> Response:
    categoria = categorias.get_categoria(db, categoria_id) if categoria_id else None
    return Response(
        equipos_import.template_csv(categoria),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plantilla-equipos.csv"'},
    )


@router.post("/importar", response_model=ImportResult)
def import_equipos(
    _: AdminUser,
    archivo: Annotated[UploadFile, File(description="CSV con un equipo por fila")],
    db: DbSession,
    dry_run: bool = True,
) -> ImportResult:
    """Con `dry_run=true` (por defecto) solo valida y muestra los errores; no guarda nada."""
    return equipos_import.import_csv(db, read_limited(archivo), dry_run=dry_run)


@router.get("/{equipo_id}", response_model=EquipoOut)
def get_equipo(_: StaffUser, equipo_id: uuid.UUID, db: DbSession) -> EquipoOut:
    return equipos.to_out(db, equipos.get_equipo(db, equipo_id))


@router.put("/{equipo_id}", response_model=EquipoOut)
def update_equipo(
    _: AdminUser, equipo_id: uuid.UUID, body: EquipoUpdate, db: DbSession
) -> EquipoOut:
    equipo = equipos.get_equipo(db, equipo_id)
    return equipos.to_out(db, equipos.update(db, equipo, body))


@router.post("/{equipo_id}/fotos", response_model=FotoOut, status_code=status.HTTP_201_CREATED)
def add_foto(
    _: AdminUser,
    equipo_id: uuid.UUID,
    foto: Annotated[UploadFile, File(description="JPG, PNG o WebP")],
    db: DbSession,
    storage: StorageDep,
) -> FotoOut:
    equipo = equipos.get_equipo(db, equipo_id)
    return FotoOut.model_validate(equipos.add_photo(db, storage, equipo, read_limited(foto)))


@router.delete("/{equipo_id}/fotos/{foto_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_foto(
    _: AdminUser, equipo_id: uuid.UUID, foto_id: uuid.UUID, db: DbSession, storage: StorageDep
) -> None:
    equipos.delete_photo(db, storage, equipos.get_equipo(db, equipo_id), foto_id)

"""Catálogo de maquinaria para clientes aprobados y personal. Las fotos son de acceso abierto."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pydantic import AwareDatetime

from app.api.deps import CatalogUser, DbSession, StorageDep
from app.core.errors import InvalidInput
from app.models.equipo import Equipo, EquipoStatus
from app.models.user import Role, User
from app.schemas.common import Page
from app.schemas.disponibilidad import DisponibilidadOut, EstadoActual
from app.schemas.equipo import EquipoCatalogOut, MiRenta
from app.services import disponibilidad, equipos, rentas

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


def _neutral(situation: dict[uuid.UUID, EstadoActual]) -> dict[uuid.UUID, EstadoActual]:
    """Al cliente no se le dice por qué un equipo no está: el mantenimiento se ve «bloqueado»."""
    return {
        i: EstadoActual.BLOQUEADO if s == EstadoActual.MANTENIMIENTO else s
        for i, s in situation.items()
    }


def _present(
    db: DbSession, user: User, items: list[Equipo], window: tuple[datetime, datetime] | None
) -> list[EquipoCatalogOut]:
    """Arma las tarjetas del catálogo: situación ahora, disponibilidad del periodo y mi renta."""
    ids = [e.id for e in items]
    busy = disponibilidad.occupied_ids(db, ids, *window) if window else set()
    situation = _neutral(disponibilidad.estado_actual(db, items))
    mine = (
        rentas.open_by_equipo(db, user.empresa_id, ids)
        if user.role == Role.CLIENTE and user.empresa_id and ids
        else {}
    )
    return [
        equipos.catalog_out(
            e,
            disponible=(e.id not in busy) if window else None,
            situacion=situation[e.id],
            mi_renta=(
                MiRenta(id=mine[e.id].id, folio=mine[e.id].folio, estado=mine[e.id].estado)
                if e.id in mine
                else None
            ),
        )
        for e in items
    ]


@router.get("", response_model=Page[EquipoCatalogOut])
def list_catalogo(
    user: CatalogUser,
    db: DbSession,
    q: str | None = None,
    categoria_id: uuid.UUID | None = None,
    desde: AwareDatetime | None = None,
    hasta: AwareDatetime | None = None,
    solo_disponibles: bool = False,
    situacion: EstadoActual | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EquipoCatalogOut]:
    """Con `desde` y `hasta` cada equipo indica si está libre en ese periodo; con `situacion`
    solo salen los que están así ahora mismo (por ejemplo `libre` o `rentado`)."""
    window = disponibilidad.parse_window(desde, hasta)
    if solo_disponibles and window is None:
        raise InvalidInput("Para ver solo los disponibles indica desde y hasta")

    def find(limit: int, offset: int) -> tuple[list[Equipo], int]:
        return equipos.search(
            db,
            q=q,
            categoria_id=categoria_id,
            status=EquipoStatus.ACTIVO,
            libre_entre=window if solo_disponibles else None,
            limit=limit,
            offset=offset,
        )

    if situacion is None:
        items, total = find(limit, offset)
    else:
        # La flota es de decenas de equipos: se filtra por su situación y se pagina aquí.
        every, _ = find(1000, 0)
        now = _neutral(disponibilidad.estado_actual(db, every))
        matching = [e for e in every if now[e.id] == situacion]
        total = len(matching)
        items = matching[offset : offset + limit]
    return Page(items=_present(db, user, items, window), total=total)


@router.get("/{equipo_id}", response_model=EquipoCatalogOut)
def get_catalogo(user: CatalogUser, equipo_id: uuid.UUID, db: DbSession) -> EquipoCatalogOut:
    return _present(db, user, [equipos.get_active_equipo(db, equipo_id)], None)[0]


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

"""Disponibilidad de equipos y bloqueos por periodo (reservas provisionales, rentas, servicio).

Un bloqueo "bloquea" mientras esté `activo` y, si es provisional, no haya vencido. La restricción
de exclusión de la base de datos solo mira `estado`, así que antes de insertar se marcan como
vencidos los provisionales caducados del equipo. Las consultas de lectura no necesitan eso: filtran
por `vence_en` directamente.
"""

import uuid
from datetime import datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import ColumnElement, and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Conflict, InvalidInput, NotFound
from app.models.bloqueo import HOLD_TYPES, Bloqueo, BloqueoEstado, BloqueoTipo
from app.models.equipo import Equipo, EquipoStatus
from app.models.user import User
from app.schemas.disponibilidad import BloqueoOut, EstadoActual, Ocupacion, Periodo

_UNAVAILABLE = "El equipo no está disponible en ese periodo"
_EXCLUSION_VIOLATION = "23P01"

_ESTADO_BY_TIPO = {
    BloqueoTipo.RENTA: EstadoActual.RENTADO,
    BloqueoTipo.SOLICITUD: EstadoActual.BLOQUEADO,
    BloqueoTipo.APARTADO: EstadoActual.BLOQUEADO,
    BloqueoTipo.MANUAL: EstadoActual.BLOQUEADO,
    BloqueoTipo.MANTENIMIENTO: EstadoActual.MANTENIMIENTO,
}


def db_now(db: Session) -> datetime:
    """Hora de la base de datos: una sola referencia para todas las instancias de la API."""
    now: datetime | None = db.scalar(select(func.now()))
    assert now is not None
    return now


def period(desde: datetime, hasta: datetime | None) -> Range[datetime]:
    """Rango [desde, hasta); sin `hasta` queda abierto hacia el futuro."""
    return Range(desde, hasta, bounds="[)")


def _live() -> ColumnElement[bool]:
    """Bloqueos que de verdad impiden usar el equipo en este momento."""
    return and_(
        Bloqueo.estado == BloqueoEstado.ACTIVO,
        or_(Bloqueo.vence_en.is_(None), Bloqueo.vence_en > func.now()),
    )


def overlapping(
    db: Session, equipo_id: uuid.UUID, desde: datetime, hasta: datetime
) -> list[Bloqueo]:
    query = (
        select(Bloqueo)
        .where(
            Bloqueo.equipo_id == equipo_id, _live(), Bloqueo.periodo.overlaps(period(desde, hasta))
        )
        .order_by(Bloqueo.periodo)
    )
    return list(db.scalars(query))


def parse_window(
    desde: datetime | None, hasta: datetime | None
) -> tuple[datetime, datetime] | None:
    """Valida un periodo consultado: o vienen `desde` y `hasta` juntos, o ninguno."""
    if desde is None and hasta is None:
        return None
    if desde is None or hasta is None:
        raise InvalidInput("Indica desde y hasta para consultar un periodo")
    try:
        periodo = Periodo(desde=desde, hasta=hasta)
    except ValidationError as exc:
        raise InvalidInput(str(exc.errors()[0]["msg"]).removeprefix("Value error, ")) from None
    return periodo.desde, periodo.hasta


def is_free(db: Session, equipo: Equipo, desde: datetime, hasta: datetime) -> bool:
    return equipo.status == EquipoStatus.ACTIVO and not overlapping(db, equipo.id, desde, hasta)


def occupied_ids(
    db: Session, equipo_ids: list[uuid.UUID], desde: datetime, hasta: datetime
) -> set[uuid.UUID]:
    """De estos equipos, los que tienen algún bloqueo en el periodo (una sola consulta)."""
    if not equipo_ids:
        return set()
    query = select(Bloqueo.equipo_id).where(
        Bloqueo.equipo_id.in_(equipo_ids), _live(), Bloqueo.periodo.overlaps(period(desde, hasta))
    )
    return set(db.scalars(query))


def free_between(desde: datetime, hasta: datetime) -> ColumnElement[bool]:
    """Condición SQL «el equipo no tiene bloqueos en el periodo» (para filtrar el catálogo)."""
    return ~exists().where(
        Bloqueo.equipo_id == Equipo.id, _live(), Bloqueo.periodo.overlaps(period(desde, hasta))
    )


def estado_actual(db: Session, equipos: list[Equipo]) -> dict[uuid.UUID, EstadoActual]:
    """Situación de cada equipo ahora mismo (una sola consulta para toda la lista)."""
    result: dict[uuid.UUID, EstadoActual] = {}
    active = []
    for equipo in equipos:
        if equipo.status == EquipoStatus.BAJA:
            result[equipo.id] = EstadoActual.BAJA
        elif equipo.status == EquipoStatus.MANTENIMIENTO:
            result[equipo.id] = EstadoActual.MANTENIMIENTO
        else:
            result[equipo.id] = EstadoActual.LIBRE
            active.append(equipo.id)
    if active:
        now = db_now(db)
        rows = db.execute(
            select(Bloqueo.equipo_id, Bloqueo.tipo).where(
                Bloqueo.equipo_id.in_(active), _live(), Bloqueo.periodo.contains(now)
            )
        )
        for equipo_id, tipo in rows:
            result[equipo_id] = _ESTADO_BY_TIPO[tipo]
    return result


def occupations(
    db: Session, equipo_id: uuid.UUID, desde: datetime, hasta: datetime
) -> list[Ocupacion]:
    return [
        Ocupacion(desde=b.desde, hasta=b.hasta) for b in overlapping(db, equipo_id, desde, hasta)
    ]


# ---------------------------------------------------------------------- escritura


def expire_holds(db: Session, equipo_id: uuid.UUID | None = None) -> int:
    """Marca como `expirado` los provisionales vencidos. Devuelve cuántos fueron."""
    statement = (
        update(Bloqueo)
        .where(Bloqueo.estado == BloqueoEstado.ACTIVO, Bloqueo.vence_en <= func.now())
        .values(estado=BloqueoEstado.EXPIRADO)
    )
    if equipo_id:
        statement = statement.where(Bloqueo.equipo_id == equipo_id)
    return len(db.execute(statement.returning(Bloqueo.id)).all())


def _insert(
    db: Session,
    equipo: Equipo,
    tipo: BloqueoTipo,
    desde: datetime,
    hasta: datetime,
    *,
    vence_en: datetime | None = None,
    motivo: str | None = None,
    user: User | None = None,
) -> Bloqueo:
    expire_holds(db, equipo.id)
    bloqueo = Bloqueo(
        equipo_id=equipo.id,
        tipo=tipo,
        periodo=period(desde, hasta),
        vence_en=vence_en,
        motivo=motivo,
        creado_por_id=user.id if user else None,
    )
    db.add(bloqueo)
    try:
        db.flush()  # aquí actúa la restricción de exclusión si alguien se adelantó
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) == _EXCLUSION_VIOLATION:
            raise Conflict(_UNAVAILABLE) from None
        raise
    return bloqueo


def block(
    db: Session,
    equipo: Equipo,
    tipo: BloqueoTipo,
    desde: datetime,
    hasta: datetime,
    motivo: str,
    user: User,
) -> Bloqueo:
    """Bloqueo del personal (mantenimiento programado u otra razón)."""
    bloqueo = _insert(db, equipo, tipo, desde, hasta, motivo=motivo, user=user)
    db.commit()
    return bloqueo


def place_hold(
    db: Session,
    equipo: Equipo,
    desde: datetime,
    hasta: datetime,
    user: User,
    *,
    commit: bool = True,
) -> Bloqueo:
    """Reserva provisional mientras ventas cotiza. Vence sola a los 20 min.

    Con `commit=False` solo se aparta (flush) y quien llama decide cuándo confirmar: así la
    reserva y la renta que la usa se guardan juntas o no se guarda nada.
    """
    if equipo.status != EquipoStatus.ACTIVO:
        raise Conflict(_UNAVAILABLE)
    minutes = get_settings().hold_solicitud_minutes
    bloqueo = _insert(
        db,
        equipo,
        BloqueoTipo.SOLICITUD,
        desde,
        hasta,
        vence_en=db_now(db) + timedelta(minutes=minutes),
        user=user,
    )
    if commit:
        db.commit()
    return bloqueo


def _live_hold(db: Session, bloqueo: Bloqueo, expected: BloqueoTipo) -> None:
    if bloqueo.tipo != expected or bloqueo.estado != BloqueoEstado.ACTIVO:
        raise Conflict("Este bloqueo ya no está en el estado esperado")
    if bloqueo.vence_en is not None and bloqueo.vence_en <= db_now(db):
        bloqueo.estado = BloqueoEstado.EXPIRADO
        db.commit()
        raise Conflict("La reserva venció; hay que volver a solicitar el equipo")


def promote_to_apartado(db: Session, bloqueo: Bloqueo) -> Bloqueo:
    """La cotización fue aceptada: se aparta el equipo por más tiempo (3 h) mientras se cumplen
    los requisitos y llega el anticipo."""
    _live_hold(db, bloqueo, BloqueoTipo.SOLICITUD)
    bloqueo.tipo = BloqueoTipo.APARTADO
    bloqueo.vence_en = db_now(db) + timedelta(minutes=get_settings().hold_apartado_minutes)
    db.commit()
    return bloqueo


def confirm_rental(db: Session, bloqueo: Bloqueo) -> Bloqueo:
    """Se cumplieron los requisitos: la renta queda firme y deja de vencer."""
    _live_hold(db, bloqueo, BloqueoTipo.APARTADO)
    bloqueo.tipo = BloqueoTipo.RENTA
    bloqueo.vence_en = None
    db.commit()
    return bloqueo


def release(db: Session, bloqueo: Bloqueo) -> None:
    if bloqueo.estado != BloqueoEstado.ACTIVO:
        raise Conflict("Este bloqueo ya no está activo")
    bloqueo.estado = BloqueoEstado.LIBERADO
    db.commit()


def release_staff_block(db: Session, bloqueo_id: uuid.UUID) -> None:
    """Libera un bloqueo del personal. Los de una renta se liberan desde la renta."""
    bloqueo = db.get(Bloqueo, bloqueo_id)
    if bloqueo is None:
        raise NotFound("Bloqueo no encontrado")
    if bloqueo.tipo in HOLD_TYPES or bloqueo.tipo == BloqueoTipo.RENTA:
        raise Conflict("Este bloqueo pertenece a una renta; se libera desde la renta")
    release(db, bloqueo)


def upcoming(db: Session, equipo_id: uuid.UUID) -> list[BloqueoOut]:
    """Bloqueos vigentes o futuros de un equipo, para el personal."""
    query = (
        select(Bloqueo)
        .where(
            Bloqueo.equipo_id == equipo_id,
            _live(),
            Bloqueo.periodo.overlaps(period(db_now(db), None)),
        )
        .order_by(Bloqueo.periodo)
    )
    return [to_out(b) for b in db.scalars(query)]


def to_out(bloqueo: Bloqueo) -> BloqueoOut:
    return BloqueoOut(
        id=bloqueo.id,
        equipo_id=bloqueo.equipo_id,
        tipo=bloqueo.tipo,
        estado=bloqueo.estado,
        desde=bloqueo.desde,
        hasta=bloqueo.hasta,
        vence_en=bloqueo.vence_en,
        motivo=bloqueo.motivo,
        creado_por_nombre=bloqueo.creado_por.full_name if bloqueo.creado_por else None,
    )

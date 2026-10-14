"""Salida y regreso del equipo: horómetro y foto del tablero, con el estado de la renta."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import Conflict, InvalidInput
from app.models.bloqueo import BloqueoEstado
from app.models.equipo import EquipoStatus
from app.models.movimiento import MovimientoTipo, RentaMovimiento
from app.models.renta import Renta, RentaEstado
from app.models.user import User
from app.schemas.movimiento import MovimientoIn, MovimientoOut, MovimientosOut
from app.services import cumplimiento, images
from app.services.storage import PrivateStorage


def find(renta: Renta, tipo: MovimientoTipo) -> RentaMovimiento | None:
    return next((m for m in renta.movimientos if m.tipo == tipo), None)


def hours_used(renta: Renta) -> Decimal | None:
    salida, regreso = find(renta, MovimientoTipo.SALIDA), find(renta, MovimientoTipo.REGRESO)
    if salida is None or regreso is None:
        return None
    return regreso.horometro - salida.horometro


def register(
    db: Session,
    storage: PrivateStorage,
    renta: Renta,
    staff: User,
    data: MovimientoIn,
    photo: bytes,
) -> RentaMovimiento:
    """Registra la salida (renta confirmada) o el regreso (renta en curso).

    La salida pasa la renta a `en_renta`; el regreso la pasa a `devuelta`, libera el equipo para
    otras rentas y, si ya no hay saldo, la cierra.
    """
    cumplimiento.lock_renta(db, renta)
    full, _ = images.process_photo(photo)  # falla antes de tocar nada si la foto no sirve
    equipo = renta.equipo
    if data.tipo == MovimientoTipo.SALIDA:
        if renta.estado != RentaEstado.CONFIRMADA:
            raise Conflict("Solo se entrega un equipo de una renta confirmada")
        if equipo.status != EquipoStatus.ACTIVO:
            raise Conflict("El equipo no está activo: revisa su estado antes de entregarlo")
        if data.horometro < equipo.horometro:
            raise InvalidInput(
                f"El horómetro no puede ser menor al último registrado ({equipo.horometro} h)"
            )
        renta.estado = RentaEstado.EN_RENTA
    else:
        if renta.estado != RentaEstado.EN_RENTA:
            raise Conflict("Solo se recibe un equipo que está en renta")
        salida = find(renta, MovimientoTipo.SALIDA)
        assert salida is not None  # EN_RENTA solo se alcanza registrando la salida
        if data.horometro < salida.horometro:
            raise InvalidInput(
                f"El horómetro no puede ser menor al de la salida ({salida.horometro} h)"
            )
        renta.estado = RentaEstado.DEVUELTA
        if renta.bloqueo is not None and renta.bloqueo.estado == BloqueoEstado.ACTIVO:
            renta.bloqueo.estado = BloqueoEstado.LIBERADO  # el equipo ya está libre
    key = storage.save(full, "jpg")
    movimiento = RentaMovimiento(
        tipo=data.tipo,
        horometro=data.horometro,
        foto_key=key,
        notas=data.notas,
        registrado_por_id=staff.id,
    )
    renta.movimientos.append(movimiento)
    equipo.horometro = data.horometro
    if data.tipo == MovimientoTipo.REGRESO:
        cumplimiento.try_close(renta)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return movimiento


def to_out(movimiento: RentaMovimiento) -> MovimientoOut:
    return MovimientoOut(
        id=movimiento.id,
        tipo=movimiento.tipo,
        horometro=movimiento.horometro,
        notas=movimiento.notas,
        registrado_por_nombre=movimiento.registrado_por.full_name,
        created_at=movimiento.created_at,
    )


def listing(renta: Renta) -> MovimientosOut:
    return MovimientosOut(
        movimientos=[to_out(m) for m in renta.movimientos], horas_usadas=hours_used(renta)
    )

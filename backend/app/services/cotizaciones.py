"""Cotizaciones: ventas cotiza; el cliente acepta (se aparta el equipo 3 h) o rechaza."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Conflict, NotFound
from app.models.bloqueo import BloqueoEstado, BloqueoTipo
from app.models.cotizacion import Cotizacion, CotizacionEstado, CotizacionPartida
from app.models.renta import Renta, RentaEstado
from app.models.user import User
from app.schemas.cotizacion import (
    CotizacionCalculo,
    CotizacionIn,
    CotizacionOut,
    CotizacionSugerida,
    PartidaOut,
)
from app.services import cotizador, disponibilidad

_ALIVE = (CotizacionEstado.VIGENTE, CotizacionEstado.ACEPTADA)


def current(renta: Renta) -> Cotizacion | None:
    """La cotización viva (vigente o ya aceptada), si hay."""
    return next((c for c in renta.cotizaciones if c.estado in _ALIVE), None)


def require_current(renta: Renta) -> Cotizacion:
    cotizacion = current(renta)
    if cotizacion is None:
        raise NotFound("Esta renta todavía no tiene cotización")
    return cotizacion


def suggested(renta: Renta) -> CotizacionSugerida:
    settings = get_settings()
    return CotizacionSugerida(
        partidas=cotizador.suggest(renta.equipo, renta),
        iva_rate=float(settings.iva_rate),
        anticipo_default_percent=settings.anticipo_default_percent,
        valida_horas=settings.cotizacion_valida_horas,
    )


def calculate(data: CotizacionIn) -> CotizacionCalculo:
    """Importes, totales y anticipo de una cotización. Es la única aritmética de dinero: la usan
    tanto la vista previa como el guardado, así nunca difieren."""
    settings = get_settings()
    amounts = [cotizador.importe(p.cantidad, p.precio_unitario) for p in data.partidas]
    totals = cotizador.totales(amounts, settings.iva_rate)
    anticipo = (
        data.anticipo_monto
        if data.anticipo_monto is not None
        else cotizador.default_anticipo(totals.total, settings.anticipo_default_percent)
    )
    if anticipo > totals.total:
        raise Conflict("El anticipo no puede ser mayor que el total")
    return CotizacionCalculo(
        importes=amounts,
        subtotal=totals.subtotal,
        iva=totals.iva,
        total=totals.total,
        anticipo_monto=anticipo,
    )


def create(db: Session, renta: Renta, staff: User, data: CotizacionIn) -> Cotizacion:
    """Crea una versión nueva (la anterior queda como `reemplazada`) y deja la renta `cotizada`."""
    if renta.estado not in (RentaEstado.SOLICITADA, RentaEstado.COTIZADA):
        raise Conflict("Esta solicitud ya no se puede cotizar")
    settings = get_settings()
    calculo = calculate(data)

    previous = current(renta)
    if previous is not None:
        previous.estado = CotizacionEstado.REEMPLAZADA
        db.flush()  # libera el lugar de la cotización viva antes de insertar la nueva

    hours = data.valida_horas or settings.cotizacion_valida_horas
    cotizacion = Cotizacion(
        renta_id=renta.id,
        version=len(renta.cotizaciones) + 1,
        subtotal=calculo.subtotal,
        iva=calculo.iva,
        total=calculo.total,
        anticipo_monto=calculo.anticipo_monto,
        valida_hasta=disponibilidad.db_now(db) + timedelta(hours=hours),
        notas=data.notas,
        creada_por_id=staff.id,
        partidas=[
            CotizacionPartida(
                orden=i,
                concepto=p.concepto,
                descripcion=p.descripcion,
                cantidad=p.cantidad,
                unidad=p.unidad,
                precio_unitario=p.precio_unitario,
                importe=amount,
            )
            for i, (p, amount) in enumerate(
                zip(data.partidas, calculo.importes, strict=True), start=1
            )
        ],
    )
    db.add(cotizacion)
    renta.estado = RentaEstado.COTIZADA
    db.commit()
    return cotizacion


def _ensure_apartado(db: Session, renta: Renta, user: User) -> None:
    """Aparta el equipo 3 h: promueve la reserva de la solicitud si sigue viva o, si ya venció,
    intenta reservar de nuevo (y falla si otro cliente se adelantó)."""
    bloqueo = renta.bloqueo
    alive = (
        bloqueo is not None
        and bloqueo.estado == BloqueoEstado.ACTIVO
        and bloqueo.tipo == BloqueoTipo.SOLICITUD
        and bloqueo.vence_en is not None
        and bloqueo.vence_en > disponibilidad.db_now(db)
    )
    if alive:
        assert bloqueo is not None
        disponibilidad.promote_to_apartado(db, bloqueo, commit=False)
        return
    try:
        nuevo = disponibilidad.place_hold(
            db,
            renta.equipo,
            renta.desde,
            renta.hasta,
            user,
            tipo=BloqueoTipo.APARTADO,
            commit=False,
        )
    except Conflict:
        raise Conflict(
            "El equipo ya no está disponible en esas fechas. Ventas te propondrá una alternativa."
        ) from None
    renta.bloqueo_id = nuevo.id
    renta.bloqueo = nuevo


def accept(db: Session, renta: Renta, user: User) -> Cotizacion:
    if renta.estado == RentaEstado.VENCIDA and any(
        c.estado == CotizacionEstado.VENCIDA for c in renta.cotizaciones
    ):
        raise Conflict("La cotización venció. Pide a ventas una nueva.")
    cotizacion = current(renta)
    if (
        renta.estado != RentaEstado.COTIZADA
        or cotizacion is None
        or cotizacion.estado != CotizacionEstado.VIGENTE
    ):
        raise Conflict("No hay una cotización vigente para aceptar")
    if cotizacion.valida_hasta <= disponibilidad.db_now(db):
        raise Conflict("La cotización venció. Pide a ventas una nueva.")
    _ensure_apartado(db, renta, user)
    cotizacion.estado = CotizacionEstado.ACEPTADA
    renta.estado = RentaEstado.APARTADA
    db.commit()
    return cotizacion


def _close(db: Session, renta: Renta, estado: RentaEstado, motivo: str) -> None:
    """Cierra la solicitud sin avanzar: libera el equipo y cierra su cotización vigente."""
    cotizacion = current(renta)
    if cotizacion is not None and cotizacion.estado == CotizacionEstado.VIGENTE:
        cotizacion.estado = CotizacionEstado.RECHAZADA
    if renta.bloqueo is not None and renta.bloqueo.estado == BloqueoEstado.ACTIVO:
        renta.bloqueo.estado = BloqueoEstado.LIBERADO
    renta.estado = estado
    renta.motivo_cierre = motivo
    db.commit()


def decline(db: Session, renta: Renta) -> None:
    """El cliente no acepta la cotización."""
    cotizacion = current(renta)
    if renta.estado != RentaEstado.COTIZADA or cotizacion is None:
        raise Conflict("No hay una cotización vigente para rechazar")
    _close(db, renta, RentaEstado.CANCELADA, "El cliente rechazó la cotización")


def reject_request(db: Session, renta: Renta, motivo: str) -> None:
    """Ventas no puede atender la solicitud."""
    if renta.estado not in (RentaEstado.SOLICITADA, RentaEstado.COTIZADA):
        raise Conflict("Esta solicitud ya no se puede rechazar")
    _close(db, renta, RentaEstado.RECHAZADA, motivo)


def to_out(cotizacion: Cotizacion) -> CotizacionOut:
    return CotizacionOut(
        id=cotizacion.id,
        renta_id=cotizacion.renta_id,
        version=cotizacion.version,
        estado=cotizacion.estado,
        partidas=[PartidaOut.model_validate(p) for p in cotizacion.partidas],
        subtotal=cotizacion.subtotal,
        iva=cotizacion.iva,
        total=cotizacion.total,
        anticipo_monto=cotizacion.anticipo_monto,
        valida_hasta=cotizacion.valida_hasta,
        notas=cotizacion.notas,
        creada_por_nombre=cotizacion.creada_por.full_name if cotizacion.creada_por else None,
        created_at=cotizacion.created_at,
    )

"""Cifras del panel del administrador: cobrado, gastado, flota y lo que requiere atención."""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Date, cast, func, select
from sqlalchemy.orm import Session

from app.core.clock import today
from app.core.config import get_settings
from app.models.cotizacion import Cotizacion, CotizacionEstado
from app.models.cumplimiento import Pago, RevisionEstado
from app.models.empresa import Empresa, EmpresaStatus
from app.models.equipo import Equipo, EquipoStatus
from app.models.gasto import Gasto
from app.models.renta import Renta, RentaEstado
from app.schemas.dashboard import (
    Comparativo,
    DashboardOut,
    EquipoIngreso,
    Flota,
    GastoCategoriaTotal,
    Mantenimiento,
    ProximaSalida,
    PuntoMensual,
    RentasEstadoTotal,
)
from app.schemas.disponibilidad import EstadoActual
from app.services import cobranza, disponibilidad, mantenimiento

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGO = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
# Estados que cuentan para la gráfica de rentas (las que no avanzaron no son actividad).
_ACTIVAS = (
    RentaEstado.SOLICITADA,
    RentaEstado.COTIZADA,
    RentaEstado.APARTADA,
    RentaEstado.CONFIRMADA,
    RentaEstado.EN_RENTA,
    RentaEstado.DEVUELTA,
    RentaEstado.CERRADA,
)


def add_months(first: date, months: int) -> date:
    index = first.year * 12 + first.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def comparativo(actual: Decimal, anterior: Decimal) -> Comparativo:
    cambio = None if anterior == 0 else float((actual - anterior) / abs(anterior) * 100)
    return Comparativo(actual=actual, anterior=anterior, cambio_pct=cambio)


def _by_month(
    db: Session, column: Any, amount: Any, *where: ColumnElement[bool]
) -> dict[date, Decimal]:
    """Suma de `amount` por mes (primer día del mes) de las filas que cumplen `where`."""
    month = cast(func.date_trunc("month", column), Date)
    rows = db.execute(select(month, func.sum(amount)).where(*where).group_by(month))
    return {m: Decimal(total) for m, total in rows}


def _pending_companies(db: Session) -> int:
    query = (
        select(func.count()).select_from(Empresa).where(Empresa.status == EmpresaStatus.PENDIENTE)
    )
    return db.scalar(query) or 0


def summary(db: Session) -> DashboardOut:
    hoy = today()
    first = hoy.replace(day=1)
    previous = add_months(first, -1)
    window_start = add_months(first, -5)
    window_end = add_months(first, 1)

    paid = Pago.estado == RevisionEstado.APROBADO
    ingresos = _by_month(
        db,
        Pago.fecha_pago,
        Pago.monto,
        paid,
        Pago.fecha_pago >= window_start,
        Pago.fecha_pago < window_end,
    )
    gastos = _by_month(
        db, Gasto.fecha, Gasto.monto, Gasto.fecha >= window_start, Gasto.fecha < window_end
    )
    zero = Decimal(0)
    serie = []
    for offset in range(6):
        month = add_months(window_start, offset)
        income, spent = ingresos.get(month, zero), gastos.get(month, zero)
        serie.append(
            PuntoMensual(
                mes=f"{month:%Y-%m}",
                etiqueta=MESES[month.month - 1],
                ingresos=income,
                gastos=spent,
                ganancia=income - spent,
            )
        )
    this, before = serie[-1], serie[-2]

    local_date = cast(func.timezone(get_settings().timezone, Cotizacion.updated_at), Date)
    sold = _by_month(
        db,
        local_date,
        Cotizacion.total,
        Cotizacion.estado == CotizacionEstado.ACEPTADA,
        local_date >= previous,
        local_date < window_end,
    )

    by_category = db.execute(
        select(Gasto.categoria, func.sum(Gasto.monto))
        .where(Gasto.fecha >= first, Gasto.fecha < window_end)
        .group_by(Gasto.categoria)
        .order_by(func.sum(Gasto.monto).desc())
    )
    top = db.execute(
        select(Equipo.id, Equipo.codigo, Equipo.nombre, func.sum(Pago.monto).label("total"))
        .join(Renta, Renta.equipo_id == Equipo.id)
        .join(Pago, Pago.renta_id == Renta.id)
        .where(paid, Pago.fecha_pago >= first, Pago.fecha_pago < window_end)
        .group_by(Equipo.id)
        .order_by(func.sum(Pago.monto).desc())
        .limit(5)
    )
    states = db.execute(
        select(Renta.estado, func.count()).where(Renta.estado.in_(_ACTIVAS)).group_by(Renta.estado)
    )
    next_out = db.execute(
        select(Renta.id, Renta.folio, Equipo.nombre, Empresa.razon_social, Renta.desde)
        .join(Equipo, Renta.equipo_id == Equipo.id)
        .join(Empresa, Renta.empresa_id == Empresa.id)
        .where(Renta.estado == RentaEstado.CONFIRMADA)
        .order_by(Renta.desde)
        .limit(5)
    )

    fleet = list(db.scalars(select(Equipo).where(Equipo.status == EquipoStatus.ACTIVO)))
    situation = disponibilidad.estado_actual(db, fleet)
    rented = sum(1 for s in situation.values() if s == EstadoActual.RENTADO)
    blocked = sum(1 for s in situation.values() if s == EstadoActual.BLOQUEADO)
    attention = mantenimiento.attention(db, only_due=True)
    billing = cobranza.summary(db, estado=None, q=None, only_balance=False)

    return DashboardOut(
        mes=f"{first:%Y-%m}",
        mes_nombre=f"{MESES_LARGO[first.month - 1]} {first.year}",
        ingresos=comparativo(this.ingresos, before.ingresos),
        gastos=comparativo(this.gastos, before.gastos),
        ganancia=comparativo(this.ganancia, before.ganancia),
        vendido=comparativo(sold.get(first, zero), sold.get(previous, zero)),
        por_cobrar=billing.saldo,
        pagos_por_confirmar=billing.pagos_por_confirmar,
        empresas_pendientes=_pending_companies(db),
        mantenimiento=Mantenimiento(
            vencidos=sum(1 for i in attention if i.estado == "vencido"),
            proximos=sum(1 for i in attention if i.estado == "proximo"),
        ),
        flota=Flota(
            total=len(fleet),
            rentados=rented,
            bloqueados=blocked,
            libres=len(fleet) - rented - blocked,
            utilizacion_pct=round(rented / len(fleet) * 100, 1) if fleet else 0.0,
        ),
        serie_mensual=serie,
        rentas_por_estado=[RentasEstadoTotal(estado=e, total=n) for e, n in states],
        gastos_por_categoria=[GastoCategoriaTotal(categoria=c, total=t) for c, t in by_category],
        top_equipos=[
            EquipoIngreso(equipo_id=i, codigo=c, nombre=n, ingresos=t) for i, c, n, t in top
        ],
        proximas_salidas=[
            ProximaSalida(renta_id=i, folio=f, equipo=e, empresa=em, desde=d)
            for i, f, e, em, d in next_out
        ],
    )

"""Aritmética de cotizaciones y renglones sugeridos. Funciones puras, sin base de datos."""

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from app.models.cotizacion import PartidaConcepto, PartidaUnidad
from app.models.equipo import Equipo
from app.models.renta import OperadorModo, Renta, Transporte
from app.schemas.cotizacion import PartidaIn

_CENT = Decimal("0.01")


@dataclass(frozen=True)
class Totales:
    subtotal: Decimal
    iva: Decimal
    total: Decimal


def money(value: Decimal) -> Decimal:
    """Redondea a centavos (mitad hacia arriba, como en una factura)."""
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def importe(cantidad: Decimal, precio_unitario: Decimal) -> Decimal:
    return money(cantidad * precio_unitario)


def totales(importes: list[Decimal], iva_rate: Decimal) -> Totales:
    subtotal = money(sum(importes, Decimal(0)))
    iva = money(subtotal * iva_rate)
    return Totales(subtotal=subtotal, iva=iva, total=subtotal + iva)


def default_anticipo(total: Decimal, percent: int) -> Decimal:
    return money(total * percent / 100)


def billable_units(desde: datetime, hasta: datetime) -> tuple[int, int]:
    """(horas, días) que se cobran: se redondea hacia arriba, mínimo 1 de cada una."""
    hours = max(1, math.ceil((hasta - desde).total_seconds() / 3600))
    return hours, math.ceil(hours / 24)


def suggest(equipo: Equipo, renta: Renta) -> list[PartidaIn]:
    """Renglones con los que ventas puede empezar. Los precios de servicios van en cero: los
    llena ventas según distancia y condiciones."""
    hours, days = billable_units(renta.desde, renta.hasta)
    options: list[tuple[Decimal, int, PartidaUnidad, Decimal]] = []
    if equipo.tarifa_hora is not None:
        options.append((equipo.tarifa_hora * hours, hours, PartidaUnidad.HORA, equipo.tarifa_hora))
    if equipo.tarifa_dia is not None:
        options.append((equipo.tarifa_dia * days, days, PartidaUnidad.DIA, equipo.tarifa_dia))
    _, quantity, unit, price = min(options, key=lambda option: option[0])  # lo más barato

    items = [
        PartidaIn(
            concepto=PartidaConcepto.RENTA,
            descripcion=f"Renta de {equipo.nombre} ({equipo.codigo})",
            cantidad=Decimal(quantity),
            unidad=unit,
            precio_unitario=price,
        )
    ]
    if renta.transporte == Transporte.ENTREGA:
        traslado = "Flete en lowboy" if equipo.requiere_lowboy else "Entrega"
        items.append(
            PartidaIn(
                concepto=PartidaConcepto.FLETE,
                descripcion=f"{traslado} a {renta.destino}",
                cantidad=Decimal(1),
                unidad=PartidaUnidad.SERVICIO,
                precio_unitario=Decimal(0),
            )
        )
    if renta.operador_modo == OperadorModo.CHRISCO:
        items.append(
            PartidaIn(
                concepto=PartidaConcepto.OPERADOR,
                descripcion="Operador de CHRISCO",
                cantidad=Decimal(hours),
                unidad=PartidaUnidad.HORA,
                precio_unitario=Decimal(0),
            )
        )
    return items

"""Aritmética de cotizaciones y renglones sugeridos (puras, sin base de datos)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.cotizacion import PartidaConcepto, PartidaUnidad
from app.models.renta import OperadorModo, Transporte
from app.services import cotizador

D = Decimal
T0 = datetime(2030, 5, 1, 8, 0, tzinfo=UTC)


def test_money_redondea_a_centavos_hacia_arriba() -> None:
    assert cotizador.money(D("1.004")) == D("1.00")
    assert cotizador.money(D("1.005")) == D("1.01")  # como en una factura, no «al par»
    assert cotizador.money(D("2.675")) == D("2.68")
    assert cotizador.money(D("10")) == D("10.00")


def test_importe_es_cantidad_por_precio_redondeado() -> None:
    assert cotizador.importe(D("8"), D("3400")) == D("27200.00")
    assert cotizador.importe(D("2.5"), D("3400.33")) == D("8500.83")  # 8500.825 → arriba
    assert cotizador.importe(D("1"), D("0")) == D("0.00")


def test_totales_con_iva() -> None:
    t = cotizador.totales([D("27200.00"), D("4500.00")], D("0.16"))
    assert (t.subtotal, t.iva, t.total) == (D("31700.00"), D("5072.00"), D("36772.00"))


def test_el_total_siempre_es_subtotal_mas_iva_aunque_se_redondee() -> None:
    t = cotizador.totales([D("0.03")], D("0.16"))  # 0.0048 → 0.00
    assert t.total == t.subtotal + t.iva
    t = cotizador.totales([D("33.33"), D("33.33"), D("33.34")], D("0.16"))
    assert t.total == t.subtotal + t.iva == D("116.00")


def test_totales_vacios() -> None:
    t = cotizador.totales([], D("0.16"))
    assert (t.subtotal, t.iva, t.total) == (D("0.00"), D("0.00"), D("0.00"))


def test_anticipo_por_defecto() -> None:
    assert cotizador.default_anticipo(D("36772.00"), 30) == D("11031.60")
    assert cotizador.default_anticipo(D("100.00"), 0) == D("0.00")
    assert cotizador.default_anticipo(D("100.00"), 100) == D("100.00")


@pytest.mark.parametrize(
    ("minutos", "horas", "dias"),
    [
        (1, 1, 1),
        (60, 1, 1),
        (61, 2, 1),
        (8 * 60, 8, 1),
        (24 * 60, 24, 1),
        (24 * 60 + 1, 25, 2),
        (72 * 60, 72, 3),
    ],
)
def test_unidades_cobrables_se_redondean_hacia_arriba(minutos, horas, dias) -> None:
    assert cotizador.billable_units(T0, T0 + timedelta(minutes=minutos)) == (horas, dias)


def equipo(hora=None, dia=None, lowboy=False):
    return SimpleNamespace(
        nombre="Pavimentadora MT 3000",
        codigo="EQ-001",
        tarifa_hora=D(hora) if hora is not None else None,
        tarifa_dia=D(dia) if dia is not None else None,
        requiere_lowboy=lowboy,
    )


def renta(horas=8, operador=OperadorModo.CHRISCO, transporte=Transporte.ENTREGA):
    return SimpleNamespace(
        desde=T0,
        hasta=T0 + timedelta(hours=horas),
        destino="Autopista Morelia - Guadalajara km 45",
        operador_modo=operador,
        transporte=transporte,
    )


def test_sugiere_la_tarifa_mas_barata_para_el_periodo() -> None:
    # 8 h a 3400/h = 27,200; un día a 20,000 es más barato.
    item = cotizador.suggest(equipo(hora=3400, dia=20000), renta(8))[0]
    assert (item.concepto, item.unidad, item.cantidad, item.precio_unitario) == (
        PartidaConcepto.RENTA,
        PartidaUnidad.DIA,
        D(1),
        D(20000),
    )
    # 3 h a 3400/h = 10,200: por hora conviene más que el día completo.
    item = cotizador.suggest(equipo(hora=3400, dia=20000), renta(3))[0]
    assert (item.unidad, item.cantidad) == (PartidaUnidad.HORA, D(3))


def test_sugiere_con_una_sola_tarifa() -> None:
    solo_hora = cotizador.suggest(equipo(hora=1500), renta(30))[0]
    assert (solo_hora.unidad, solo_hora.cantidad) == (PartidaUnidad.HORA, D(30))
    solo_dia = cotizador.suggest(equipo(dia=12000), renta(30))[0]
    assert (solo_dia.unidad, solo_dia.cantidad) == (PartidaUnidad.DIA, D(2))


def test_sugiere_flete_y_operador_segun_la_solicitud() -> None:
    base = cotizador.suggest(equipo(hora=1000), renta(8))
    assert [i.concepto for i in base] == [
        PartidaConcepto.RENTA,
        PartidaConcepto.FLETE,
        PartidaConcepto.OPERADOR,
    ]
    flete = base[1]
    assert flete.descripcion == "Entrega a Autopista Morelia - Guadalajara km 45"
    assert flete.precio_unitario == 0  # ventas lo llena según la distancia
    operador = base[2]
    assert (operador.unidad, operador.cantidad, operador.precio_unitario) == (
        PartidaUnidad.HORA,
        D(8),
        D(0),
    )

    lowboy = cotizador.suggest(equipo(hora=1000, lowboy=True), renta(8))
    assert lowboy[1].descripcion.startswith("Flete en lowboy a")


def test_sin_entrega_ni_operador_de_chrisco_solo_hay_renta() -> None:
    items = cotizador.suggest(equipo(hora=1000), renta(8, OperadorModo.CLIENTE, Transporte.RECOGE))
    assert [i.concepto for i in items] == [PartidaConcepto.RENTA]

"""Cobranza: total cotizado, confirmado y saldo por renta."""

import pytest

from tests.rentas_helpers import ANTICIPO, TOTAL, apartar, pedir
from tests.test_cumplimiento import pagar, revisar_pago


@pytest.fixture
def staff(admin_h, ventas_h):
    return {"admin": admin_h, "ventas": ventas_h}


def cobranza(client, headers, **params):
    return client.get("/admin/cobranza", params=params, headers=headers)


def test_sin_rentas_cobrables_todo_es_cero(client, client_h, staff, make_equipo) -> None:
    pedir(client, client_h, make_equipo()["id"])  # solo solicitada: aún no hay nada que cobrar
    body = cobranza(client, staff["ventas"]).json()
    assert body["items"] == [] and body["total"] == 0
    assert body["resumen"] == {
        "total_cotizado": 0,
        "total_pagado": 0,
        "saldo": 0,
        "pagos_por_confirmar": 0,
    }


def test_totales_por_renta_y_resumen(client, client_h, staff, make_equipo) -> None:
    a = apartar(client, client_h, staff["ventas"], make_equipo()["id"])
    apartar(client, client_h, staff["ventas"], make_equipo()["id"])
    confirmado = pagar(client, client_h, a["id"], monto=10000).json()
    revisar_pago(client, staff["ventas"], a["id"], confirmado["id"])
    pagar(client, client_h, a["id"], monto=500)  # reportado, sin confirmar

    body = cobranza(client, staff["admin"]).json()
    assert body["total"] == 2
    por_id = {i["renta_id"]: i for i in body["items"]}
    assert por_id[a["id"]]["total"] == TOTAL
    assert por_id[a["id"]]["pagado"] == 10000 and por_id[a["id"]]["saldo"] == TOTAL - 10000
    assert body["resumen"] == {
        "total_cotizado": TOTAL * 2,
        "total_pagado": 10000,
        "saldo": TOTAL * 2 - 10000,
        "pagos_por_confirmar": 1,
    }


def test_filtros(client, client_h, staff, make_equipo) -> None:
    a = apartar(client, client_h, staff["ventas"], make_equipo()["id"])
    b = apartar(client, client_h, staff["ventas"], make_equipo()["id"])
    pago = pagar(client, client_h, b["id"], monto=TOTAL).json()
    revisar_pago(client, staff["ventas"], b["id"], pago["id"])

    con_saldo = cobranza(client, staff["ventas"], solo_con_saldo="true").json()
    assert [i["renta_id"] for i in con_saldo["items"]] == [a["id"]]
    assert con_saldo["resumen"]["total_cotizado"] == TOTAL

    por_folio = cobranza(client, staff["ventas"], q=b["folio"]).json()
    assert [i["renta_id"] for i in por_folio["items"]] == [b["id"]]
    assert cobranza(client, staff["ventas"], q="no-existe-xyz").json()["items"] == []
    assert cobranza(client, staff["ventas"], estado="apartada").json()["total"] == 2
    assert cobranza(client, staff["ventas"], estado="cerrada").json()["total"] == 0


def test_paginacion(client, client_h, staff, make_equipo) -> None:
    for _ in range(3):
        apartar(client, client_h, staff["ventas"], make_equipo()["id"])
    pagina = cobranza(client, staff["ventas"], limit=2, offset=2).json()
    assert pagina["total"] == 3 and len(pagina["items"]) == 1
    assert cobranza(client, staff["ventas"], limit=0).status_code == 422


def test_solo_el_personal_ve_la_cobranza(client, client_h, otra_empresa_h) -> None:
    assert cobranza(client, client_h).status_code == 403
    assert cobranza(client, otra_empresa_h).status_code == 403
    assert client.get("/admin/cobranza").status_code == 401


def test_el_anticipo_es_el_30_por_ciento() -> None:
    assert round(TOTAL * 0.3, 2) == ANTICIPO

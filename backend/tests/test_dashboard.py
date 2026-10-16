"""Panel del administrador y gastos: cifras del mes, comparativo y gráficas."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.clock import today
from app.models.cumplimiento import Pago
from app.models.equipo import Equipo
from app.services.dashboard import add_months
from tests.rentas_helpers import ANTICIPO, TOTAL, apartar
from tests.test_cumplimiento import completar


@pytest.fixture
def staff(admin_h, ventas_h):
    return {"admin": admin_h, "ventas": ventas_h}


def panel(client, headers) -> dict:
    res = client.get("/admin/dashboard", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def gasto(
    client, headers, monto=1000, concepto="Diésel de la semana", categoria="combustible", **extra
):
    cuerpo = {
        "fecha": today().isoformat(),
        "categoria": categoria,
        "concepto": concepto,
        "monto": monto,
        **extra,
    }
    return client.post("/admin/gastos", json=cuerpo, headers=headers)


def mover_pagos_al_mes_pasado(db, renta_id) -> None:
    anterior = add_months(today().replace(day=1), -1)
    db.query(Pago).filter_by(renta_id=uuid.UUID(renta_id)).update(
        {"fecha_pago": anterior + timedelta(days=9)}
    )
    db.commit()


@pytest.fixture
def renta_cobrada(client, client_h, staff, make_equipo):
    """Renta confirmada con el anticipo cobrado hoy."""
    renta = apartar(client, client_h, staff["ventas"], make_equipo()["id"], transporte="recoge")
    completar(client, client_h, staff, renta["id"])
    return renta


# ---------------------------------------------------------------- panel


def test_panel_vacio(client, admin_h) -> None:
    p = panel(client, admin_h)
    assert p["mes"] == today().strftime("%Y-%m")
    for clave in ("ingresos", "gastos", "ganancia", "vendido"):
        assert p[clave] == {"actual": 0, "anterior": 0, "cambio_pct": None}
    assert len(p["serie_mensual"]) == 6 and p["serie_mensual"][-1]["mes"] == p["mes"]
    assert [x["etiqueta"] for x in p["serie_mensual"]][-1] in (
        "ene",
        "feb",
        "mar",
        "abr",
        "may",
        "jun",
        "jul",
        "ago",
        "sep",
        "oct",
        "nov",
        "dic",
    )
    assert p["por_cobrar"] == 0 and p["pagos_por_confirmar"] == 0 and p["empresas_pendientes"] == 0
    assert p["flota"] == {
        "total": 0,
        "rentados": 0,
        "bloqueados": 0,
        "libres": 0,
        "utilizacion_pct": 0,
    }
    assert p["top_equipos"] == [] and p["proximas_salidas"] == [] and p["rentas_por_estado"] == []


def test_ingresos_gastos_y_ganancia_del_mes(client, staff, renta_cobrada) -> None:
    assert gasto(client, staff["admin"], 900).status_code == 201
    p = panel(client, staff["ventas"])
    assert p["ingresos"]["actual"] == ANTICIPO
    assert p["gastos"]["actual"] == 900
    assert p["ganancia"]["actual"] == pytest.approx(ANTICIPO - 900)
    assert p["serie_mensual"][-1]["ganancia"] == pytest.approx(ANTICIPO - 900)
    assert p["gastos_por_categoria"] == [{"categoria": "combustible", "total": 900}]


def test_una_perdida_sale_negativa(client, staff) -> None:
    gasto(client, staff["admin"], 2500, "Refacciones de la pavimentadora", "refacciones")
    p = panel(client, staff["admin"])
    assert p["ganancia"]["actual"] == -2500 and p["ingresos"]["actual"] == 0


def test_comparativo_contra_el_mes_anterior(client, staff, renta_cobrada, db) -> None:
    mover_pagos_al_mes_pasado(db, renta_cobrada["id"])
    p = panel(client, staff["admin"])
    assert p["ingresos"] == {"actual": 0, "anterior": ANTICIPO, "cambio_pct": -100}
    assert p["serie_mensual"][-2]["ingresos"] == ANTICIPO

    # Otro cobro este mes: ahora hay contra qué comparar.
    pago = client.post(
        f"/rentas/{renta_cobrada['id']}/pagos",
        data={"monto": "1000", "fecha_pago": today().isoformat()},
        files={"comprobante": ("c.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        headers=staff["admin"],
    )
    assert pago.status_code == 403  # lo reporta el cliente, no el personal


def test_un_pago_sin_confirmar_no_cuenta_como_ingreso(client, client_h, staff, make_equipo) -> None:
    renta = apartar(client, client_h, staff["ventas"], make_equipo()["id"], transporte="recoge")
    client.post(
        f"/rentas/{renta['id']}/pagos",
        data={"monto": str(ANTICIPO), "fecha_pago": today().isoformat()},
        files={"comprobante": ("c.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        headers=client_h,
    )
    p = panel(client, staff["admin"])
    assert p["ingresos"]["actual"] == 0 and p["pagos_por_confirmar"] == 1
    assert p["por_cobrar"] == TOTAL


def test_lo_vendido_son_las_cotizaciones_aceptadas(client, staff, renta_cobrada) -> None:
    p = panel(client, staff["admin"])
    assert p["vendido"]["actual"] == TOTAL
    assert p["por_cobrar"] == pytest.approx(TOTAL - ANTICIPO)


def test_top_equipos_proximas_salidas_y_rentas_por_estado(client, staff, renta_cobrada) -> None:
    p = panel(client, staff["admin"])
    assert [e["ingresos"] for e in p["top_equipos"]] == [ANTICIPO]
    assert p["top_equipos"][0]["equipo_id"] == renta_cobrada["equipo_id"]
    assert [s["renta_id"] for s in p["proximas_salidas"]] == [renta_cobrada["id"]]
    assert p["rentas_por_estado"] == [{"estado": "confirmada", "total": 1}]


def test_flota_y_utilizacion(client, staff, make_equipo, db) -> None:
    a, b, c = make_equipo(), make_equipo(), make_equipo()
    assert panel(client, staff["admin"])["flota"] == {
        "total": 3,
        "rentados": 0,
        "bloqueados": 0,
        "libres": 3,
        "utilizacion_pct": 0,
    }
    ahora = client.post(
        f"/admin/equipos/{a['id']}/bloqueos",
        json={
            "tipo": "manual",
            "motivo": "Prueba",
            "desde": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "hasta": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
        headers=staff["admin"],
    )
    assert ahora.status_code == 201, ahora.text
    flota = panel(client, staff["admin"])["flota"]
    assert flota["total"] == 3 and flota["bloqueados"] == 1 and flota["libres"] == 2
    assert b and c


def test_alertas_de_mantenimiento_y_empresas_pendientes(
    client, staff, make_equipo, db, register
) -> None:
    equipo = make_equipo()
    db.query(Equipo).filter_by(id=uuid.UUID(equipo["id"])).update({"horometro": Decimal(1000)})
    db.commit()
    client.post(
        f"/admin/equipos/{equipo['id']}/mantenimiento",
        json={"nombre": "Aceite", "cada_horas": 250},
        headers=staff["admin"],
    )
    db.query(Equipo).filter_by(id=uuid.UUID(equipo["id"])).update({"horometro": Decimal(1260)})
    db.commit()
    register()
    p = panel(client, staff["admin"])
    assert p["mantenimiento"] == {"vencidos": 1, "proximos": 0}
    assert p["empresas_pendientes"] == 1


def test_permisos_del_panel(client, client_h, make_user, login) -> None:
    assert client.get("/admin/dashboard").status_code == 401
    assert client.get("/admin/dashboard", headers=client_h).status_code == 403


# ---------------------------------------------------------------- gastos


def test_registrar_y_listar_gastos(client, staff) -> None:
    res = gasto(client, staff["admin"], 1500.5, "Flete de la excavadora", "flete")
    assert res.status_code == 201, res.text
    assert res.json()["monto"] == 1500.5 and res.json()["registrado_por_nombre"]
    gasto(client, staff["admin"], 500, "Diésel", "combustible")
    lista = client.get("/admin/gastos", headers=staff["ventas"]).json()
    assert lista["total"] == 2 and lista["suma"] == 2000.5


def test_filtros_de_gastos(client, staff) -> None:
    mes_pasado = add_months(today().replace(day=1), -1) + timedelta(days=3)
    gasto(client, staff["admin"], 100, "Reciente", "otro")
    gasto(
        client, staff["admin"], 300, "Del mes pasado", "combustible", fecha=mes_pasado.isoformat()
    )
    este = today().strftime("%Y-%m")
    assert client.get(f"/admin/gastos?mes={este}", headers=staff["admin"]).json()["suma"] == 100
    pasado = mes_pasado.strftime("%Y-%m")
    assert client.get(f"/admin/gastos?mes={pasado}", headers=staff["admin"]).json()["suma"] == 300
    por_categoria = client.get("/admin/gastos?categoria=combustible", headers=staff["admin"]).json()
    assert por_categoria["total"] == 1 and por_categoria["suma"] == 300
    assert client.get("/admin/gastos?mes=2026-13", headers=staff["admin"]).status_code == 422


@pytest.mark.parametrize(
    "cambios",
    [
        {"monto": 0},
        {"monto": -5},
        {"concepto": "ab"},
        {"categoria": "nada"},
        {"equipo_id": str(uuid.uuid4())},
    ],
)
def test_gastos_invalidos(client, staff, cambios) -> None:
    assert gasto(client, staff["admin"], **cambios).status_code in (404, 422)


def test_un_gasto_no_puede_ser_futuro(client, staff) -> None:
    manana = (today() + timedelta(days=1)).isoformat()
    res = gasto(client, staff["admin"], fecha=manana)
    assert res.status_code == 422 and "futura" in res.json()["detail"]


def test_borrar_un_gasto_y_permisos(client, staff) -> None:
    creado = gasto(client, staff["admin"]).json()
    assert (
        client.delete(f"/admin/gastos/{creado['id']}", headers=staff["ventas"]).status_code == 403
    )
    assert gasto(client, staff["ventas"]).status_code == 403
    assert client.delete(f"/admin/gastos/{creado['id']}", headers=staff["admin"]).status_code == 204
    assert client.delete(f"/admin/gastos/{creado['id']}", headers=staff["admin"]).status_code == 404
    assert client.get("/admin/gastos", headers=staff["admin"]).json()["total"] == 0


def test_un_servicio_de_mantenimiento_con_costo_genera_un_gasto(client, staff, make_equipo) -> None:
    equipo = make_equipo()
    plan = client.post(
        f"/admin/equipos/{equipo['id']}/mantenimiento",
        json={"nombre": "Cambio de aceite", "cada_horas": 250},
        headers=staff["admin"],
    ).json()
    sin_costo = client.post(
        f"/admin/mantenimiento/{plan['id']}/realizado", json={}, headers=staff["admin"]
    )
    assert sin_costo.status_code == 201
    assert client.get("/admin/gastos", headers=staff["admin"]).json()["total"] == 0

    con_costo = client.post(
        f"/admin/mantenimiento/{plan['id']}/realizado",
        json={"costo": 3200.75, "notas": "Aceite y filtros"},
        headers=staff["admin"],
    )
    assert con_costo.status_code == 201, con_costo.text
    lista = client.get("/admin/gastos", headers=staff["admin"]).json()
    assert lista["total"] == 1 and lista["suma"] == 3200.75
    g = lista["items"][0]
    assert g["categoria"] == "mantenimiento" and g["equipo_codigo"] == equipo["codigo"]
    assert "Cambio de aceite" in g["concepto"]
    assert panel(client, staff["admin"])["gastos"]["actual"] == 3200.75


def test_un_costo_invalido_no_registra_el_servicio(client, staff, make_equipo) -> None:
    equipo = make_equipo()
    plan = client.post(
        f"/admin/equipos/{equipo['id']}/mantenimiento",
        json={"nombre": "Engrasado", "cada_dias": 30},
        headers=staff["admin"],
    ).json()
    res = client.post(
        f"/admin/mantenimiento/{plan['id']}/realizado", json={"costo": -10}, headers=staff["admin"]
    )
    assert res.status_code == 422
    assert (
        client.get(f"/admin/mantenimiento/{plan['id']}/registros", headers=staff["admin"]).json()
        == []
    )


def test_fechas_de_add_months() -> None:
    assert add_months(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert add_months(date(2026, 12, 1), 1) == date(2027, 1, 1)
    assert add_months(date(2026, 10, 1), -5) == date(2026, 5, 1)

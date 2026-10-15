"""Mantenimiento periódico: estado de cada plan y alertas por correo."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.clock import today
from app.models.equipo import Equipo, EquipoStatus
from app.models.mantenimiento import MantenimientoPlan
from app.services import mantenimiento


@pytest.fixture
def equipo(make_equipo, db):
    """Un equipo con el horómetro en 1000 h."""
    e = make_equipo()
    db.query(Equipo).filter_by(id=uuid.UUID(e["id"])).update({"horometro": Decimal(1000)})
    db.commit()
    return e


def crear(client, headers, equipo_id, **datos):
    cuerpo = {"nombre": "Cambio de aceite", "cada_horas": 250, **datos}
    return client.post(f"/admin/equipos/{equipo_id}/mantenimiento", json=cuerpo, headers=headers)


def retroceder(db, plan_id, *, horas=None, dias=None, alerta=None):
    """Simula el paso del tiempo moviendo el punto de partida del plan."""
    plan = db.get(MantenimientoPlan, uuid.UUID(plan_id))
    if horas is not None:
        plan.ultimo_horometro = plan.ultimo_horometro - Decimal(horas)
    if dias is not None:
        plan.ultima_fecha = plan.ultima_fecha - timedelta(days=dias)
    if alerta is not None:
        plan.alerta_enviada = alerta
    db.commit()


def poner_horometro(db, equipo_id, valor):
    db.query(Equipo).filter_by(id=uuid.UUID(equipo_id)).update({"horometro": Decimal(valor)})
    db.commit()


# ---------------------------------------------------------------- planes


def test_un_plan_nuevo_cuenta_desde_hoy_y_desde_el_horometro_actual(
    client, admin_h, equipo
) -> None:
    res = crear(client, admin_h, equipo["id"], cada_dias=90)
    assert res.status_code == 201, res.text
    plan = res.json()
    assert plan["ultimo_horometro"] == 1000 and plan["ultima_fecha"] == today().isoformat()
    assert plan["estado"] == "ok" and plan["faltan_horas"] == 250 and plan["faltan_dias"] == 90
    assert plan["activo"] is True


@pytest.mark.parametrize(
    "datos",
    [
        {"cada_horas": None},  # sin ningún intervalo
        {"cada_horas": 0},
        {"cada_horas": -5},
        {"cada_horas": None, "cada_dias": 0},
        {"cada_horas": None, "cada_dias": 4000},
        {"nombre": "ab"},
    ],
)
def test_planes_invalidos(client, admin_h, equipo, datos) -> None:
    assert crear(client, admin_h, equipo["id"], **datos).status_code == 422


def test_no_se_repite_el_nombre_en_un_equipo(client, admin_h, equipo, make_equipo) -> None:
    assert crear(client, admin_h, equipo["id"]).status_code == 201
    assert crear(client, admin_h, equipo["id"], nombre="cambio de ACEITE").status_code == 409
    assert crear(client, admin_h, make_equipo()["id"]).status_code == 201  # otro equipo, sí


def test_editar_y_borrar_un_plan(client, admin_h, equipo) -> None:
    plan = crear(client, admin_h, equipo["id"]).json()
    res = client.put(
        f"/admin/mantenimiento/{plan['id']}",
        json={"nombre": "Aceite y filtros", "cada_horas": 500, "activo": False},
        headers=admin_h,
    )
    assert res.status_code == 200
    assert res.json()["nombre"] == "Aceite y filtros" and res.json()["cada_horas"] == 500
    assert res.json()["activo"] is False
    assert client.delete(f"/admin/mantenimiento/{plan['id']}", headers=admin_h).status_code == 204
    assert client.get(f"/admin/equipos/{equipo['id']}/mantenimiento", headers=admin_h).json() == []
    assert client.delete(f"/admin/mantenimiento/{plan['id']}", headers=admin_h).status_code == 404


def test_ventas_ve_pero_no_cambia(client, admin_h, ventas_h, equipo) -> None:
    plan = crear(client, admin_h, equipo["id"]).json()
    assert (
        client.get(f"/admin/equipos/{equipo['id']}/mantenimiento", headers=ventas_h).status_code
        == 200
    )
    assert client.get("/admin/mantenimiento", headers=ventas_h).status_code == 200
    assert crear(client, ventas_h, equipo["id"], nombre="Otro").status_code == 403
    assert (
        client.put(
            f"/admin/mantenimiento/{plan['id']}",
            json={"nombre": "xxx", "cada_dias": 5},
            headers=ventas_h,
        ).status_code
        == 403
    )
    assert client.delete(f"/admin/mantenimiento/{plan['id']}", headers=ventas_h).status_code == 403
    cuerpo = {"horometro": 1100}
    url = f"/admin/mantenimiento/{plan['id']}/realizado"
    assert client.post(url, json=cuerpo, headers=ventas_h).status_code == 403


def test_un_cliente_no_entra(client, client_h, equipo) -> None:
    assert client.get("/admin/mantenimiento", headers=client_h).status_code == 403
    assert client.get("/admin/mantenimiento").status_code == 401


# ---------------------------------------------------------------- estado


@pytest.mark.parametrize(
    ("horas", "esperado"),
    [
        (0, "ok"),
        (199, "ok"),  # faltan 51 h
        (200, "proximo"),  # faltan 50 h: el aviso empieza aquí
        (249, "proximo"),
        (250, "vencido"),  # llegó a las 250 h
        (400, "vencido"),
    ],
)
def test_estado_por_horas(client, admin_h, equipo, db, horas, esperado) -> None:
    plan = crear(client, admin_h, equipo["id"]).json()
    poner_horometro(db, equipo["id"], 1000 + horas)
    lista = client.get(f"/admin/equipos/{equipo['id']}/mantenimiento", headers=admin_h).json()
    assert lista[0]["id"] == plan["id"] and lista[0]["estado"] == esperado
    assert lista[0]["faltan_horas"] == 250 - horas


@pytest.mark.parametrize(
    ("dias_pasados", "esperado"),
    [(0, "ok"), (74, "ok"), (76, "proximo"), (89, "proximo"), (90, "vencido"), (120, "vencido")],
)
def test_estado_por_dias(client, admin_h, equipo, db, dias_pasados, esperado) -> None:
    plan = crear(client, admin_h, equipo["id"], cada_horas=None, cada_dias=90).json()
    retroceder(db, plan["id"], dias=dias_pasados)
    lista = client.get(f"/admin/equipos/{equipo['id']}/mantenimiento", headers=admin_h).json()
    assert lista[0]["estado"] == esperado and lista[0]["faltan_dias"] == 90 - dias_pasados
    assert lista[0]["faltan_horas"] is None


def test_con_dos_intervalos_manda_el_que_primero_se_cumple(client, admin_h, equipo, db) -> None:
    plan = crear(client, admin_h, equipo["id"], cada_horas=500, cada_dias=30).json()
    retroceder(db, plan["id"], dias=31)  # por días ya venció aunque falten 500 h
    assert (
        client.get(f"/admin/equipos/{equipo['id']}/mantenimiento", headers=admin_h).json()[0][
            "estado"
        ]
        == "vencido"
    )


# ---------------------------------------------------------------- servicio realizado


def test_registrar_el_servicio_reinicia_el_conteo(client, admin_h, equipo, db) -> None:
    plan = crear(client, admin_h, equipo["id"]).json()
    poner_horometro(db, equipo["id"], 1260)  # vencido por 10 h
    url = f"/admin/mantenimiento/{plan['id']}/realizado"
    res = client.post(url, json={"horometro": 1260, "notas": "Aceite 15W40"}, headers=admin_h)
    assert res.status_code == 201, res.text
    assert res.json()["horometro"] == 1260 and res.json()["notas"] == "Aceite 15W40"
    assert res.json()["fecha"] == today().isoformat()

    estado = client.get(f"/admin/equipos/{equipo['id']}/mantenimiento", headers=admin_h).json()[0]
    assert estado["estado"] == "ok" and estado["faltan_horas"] == 250
    assert estado["ultimo_horometro"] == 1260
    historial = client.get(f"/admin/mantenimiento/{plan['id']}/registros", headers=admin_h).json()
    assert len(historial) == 1 and historial[0]["notas"] == "Aceite 15W40"


def test_sin_datos_toma_hoy_y_el_horometro_del_equipo(client, admin_h, equipo, db) -> None:
    plan = crear(client, admin_h, equipo["id"]).json()
    poner_horometro(db, equipo["id"], 1100)
    res = client.post(f"/admin/mantenimiento/{plan['id']}/realizado", json={}, headers=admin_h)
    assert res.json()["horometro"] == 1100 and res.json()["fecha"] == today().isoformat()


def test_la_fecha_del_servicio_no_puede_ser_futura(client, admin_h, equipo) -> None:
    plan = crear(client, admin_h, equipo["id"]).json()
    manana = (today() + timedelta(days=1)).isoformat()
    res = client.post(
        f"/admin/mantenimiento/{plan['id']}/realizado", json={"fecha": manana}, headers=admin_h
    )
    assert res.status_code == 422 and "futura" in res.json()["detail"]


# ---------------------------------------------------------------- vista general


def test_la_vista_general_ordena_por_urgencia_y_filtra(
    client, admin_h, equipo, make_equipo, db
) -> None:
    otro = make_equipo()
    ok = crear(client, admin_h, otro["id"], nombre="Engrasado").json()
    vencido = crear(client, admin_h, equipo["id"], nombre="Aceite").json()
    proximo = crear(client, admin_h, equipo["id"], nombre="Filtros", cada_horas=300).json()
    poner_horometro(db, equipo["id"], 1260)  # aceite vencido; filtros: faltan 40 → próximo
    todos = client.get("/admin/mantenimiento", headers=admin_h).json()
    assert [(i["id"], i["estado"]) for i in todos] == [
        (vencido["id"], "vencido"),
        (proximo["id"], "proximo"),
        (ok["id"], "ok"),
    ]
    assert todos[0]["equipo_codigo"] == equipo["codigo"] and todos[0]["horometro_actual"] == 1260
    atencion = client.get("/admin/mantenimiento?solo_atencion=true", headers=admin_h).json()
    assert [i["estado"] for i in atencion] == ["vencido", "proximo"]


def test_planes_inactivos_y_equipos_de_baja_no_cuentan(client, admin_h, equipo, db) -> None:
    plan = crear(client, admin_h, equipo["id"]).json()
    poner_horometro(db, equipo["id"], 1300)
    assert len(client.get("/admin/mantenimiento?solo_atencion=true", headers=admin_h).json()) == 1
    client.put(
        f"/admin/mantenimiento/{plan['id']}",
        json={"nombre": "Cambio de aceite", "cada_horas": 250, "activo": False},
        headers=admin_h,
    )
    assert client.get("/admin/mantenimiento?solo_atencion=true", headers=admin_h).json() == []
    client.put(
        f"/admin/mantenimiento/{plan['id']}",
        json={"nombre": "Cambio de aceite", "cada_horas": 250},
        headers=admin_h,
    )
    db.query(Equipo).filter_by(id=uuid.UUID(equipo["id"])).update({"status": EquipoStatus.BAJA})
    db.commit()
    assert client.get("/admin/mantenimiento?solo_atencion=true", headers=admin_h).json() == []


# ---------------------------------------------------------------- alertas por correo


def test_la_alerta_llega_a_los_administradores_por_correo(
    client, admin_h, ventas_h, equipo, db, outbox
) -> None:
    crear(client, admin_h, equipo["id"])
    poner_horometro(db, equipo["id"], 1260)
    assert mantenimiento.send_alerts(db, outbox) == 1
    assert [m.to for m in outbox] == ["admin@chrisco-pruebas.com"]  # ventas no es dueño
    correo = outbox[0]
    assert "1 vencido(s)" in correo.subject
    assert equipo["codigo"] in correo.body and "Cambio de aceite" in correo.body
    assert "VENCIDO" in correo.body and "se pasó por 10 h" in correo.body


def test_cada_situacion_avisa_una_sola_vez(client, admin_h, equipo, db, outbox) -> None:
    crear(client, admin_h, equipo["id"])
    assert mantenimiento.send_alerts(db, outbox) == 0  # todo en orden: no hay correo
    assert outbox == []

    poner_horometro(db, equipo["id"], 1210)  # próximo
    assert mantenimiento.send_alerts(db, outbox) == 1
    assert mantenimiento.send_alerts(db, outbox) == 0  # el mismo aviso no se repite
    assert len(outbox) == 1 and "próximo" in outbox[0].subject

    poner_horometro(db, equipo["id"], 1255)  # escala a vencido: avisa otra vez
    assert mantenimiento.send_alerts(db, outbox) == 1
    assert len(outbox) == 2 and "vencido" in outbox[1].subject
    assert mantenimiento.send_alerts(db, outbox) == 0


def test_al_registrar_el_servicio_se_rearma_el_aviso(client, admin_h, equipo, db, outbox) -> None:
    plan = crear(client, admin_h, equipo["id"]).json()
    poner_horometro(db, equipo["id"], 1255)
    mantenimiento.send_alerts(db, outbox)
    client.post(f"/admin/mantenimiento/{plan['id']}/realizado", json={}, headers=admin_h)
    poner_horometro(db, equipo["id"], 1255 + 249)  # vuelve a estar próximo
    assert mantenimiento.send_alerts(db, outbox) == 1
    assert len(outbox) == 2


def test_un_solo_correo_con_todo_lo_pendiente(
    client, admin_h, equipo, make_equipo, db, outbox
) -> None:
    otro = make_equipo()
    crear(client, admin_h, equipo["id"], nombre="Aceite")
    crear(client, admin_h, otro["id"], nombre="Engrasado", cada_dias=10)
    poner_horometro(db, equipo["id"], 1260)
    retroceder(
        db,
        client.get(f"/admin/equipos/{otro['id']}/mantenimiento", headers=admin_h).json()[0]["id"],
        dias=11,
    )
    assert mantenimiento.send_alerts(db, outbox) == 2
    assert len(outbox) == 1
    assert "Aceite" in outbox[0].body and "Engrasado" in outbox[0].body
    assert "2 vencido(s)" in outbox[0].subject


def test_si_el_correo_falla_no_se_marca_como_avisado(client, admin_h, equipo, db) -> None:
    class Roto:
        def send(self, mail) -> None:
            raise RuntimeError("sin red")

    crear(client, admin_h, equipo["id"])
    poner_horometro(db, equipo["id"], 1260)
    with pytest.raises(RuntimeError):
        mantenimiento.send_alerts(db, Roto())
    db.rollback()
    assert db.query(MantenimientoPlan).one().alerta_enviada is None


def test_sin_administradores_activos_no_hay_a_quien_avisar(
    client, admin_h, equipo, db, outbox
) -> None:
    from app.models.user import User

    crear(client, admin_h, equipo["id"])
    poner_horometro(db, equipo["id"], 1260)
    db.query(User).update({"is_active": False})
    db.commit()
    assert mantenimiento.send_alerts(db, outbox) == 0
    assert outbox == []
    assert db.query(MantenimientoPlan).one().alerta_enviada is None


def test_corregir_el_intervalo_rearma_el_aviso(client, admin_h, equipo, db, outbox) -> None:
    plan = crear(client, admin_h, equipo["id"]).json()
    poner_horometro(db, equipo["id"], 1260)
    mantenimiento.send_alerts(db, outbox)
    client.put(
        f"/admin/mantenimiento/{plan['id']}",
        json={"nombre": "Cambio de aceite", "cada_horas": 1000},
        headers=admin_h,
    )
    assert mantenimiento.send_alerts(db, outbox) == 0  # ya está en orden
    assert db.query(MantenimientoPlan).one().alerta_enviada is None


def test_situacion_es_pura_y_usa_los_umbrales(db) -> None:
    plan = MantenimientoPlan(
        nombre="x",
        cada_horas=Decimal(100),
        cada_dias=None,
        ultimo_horometro=Decimal(0),
        ultima_fecha=date(2026, 1, 1),
    )
    assert mantenimiento.situacion(plan, Decimal(49), date(2026, 1, 2)).estado == "ok"
    assert mantenimiento.situacion(plan, Decimal(51), date(2026, 1, 2)).estado == "proximo"
    assert mantenimiento.situacion(plan, Decimal(100), date(2026, 1, 2)).estado == "vencido"

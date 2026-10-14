import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.bloqueo import Bloqueo, BloqueoEstado, BloqueoTipo
from app.models.cotizacion import CotizacionEstado
from app.models.renta import Renta, RentaEstado
from tests.conftest import equipo_payload
from tests.rentas_helpers import pedir, vencer

PARTIDAS = [
    {
        "concepto": "renta",
        "descripcion": "Renta de Pavimentadora 1",
        "cantidad": 8,
        "unidad": "hora",
        "precio_unitario": 3400,
    },
    {
        "concepto": "flete",
        "descripcion": "Flete en lowboy a la obra",
        "cantidad": 1,
        "unidad": "servicio",
        "precio_unitario": 4500,
    },
]
# 8 × 3400 + 4500 = 31,700 → IVA 5,072 → total 36,772 → anticipo 30 % = 11,031.60


def cotizar(client, headers, renta_id, partidas=None, **extra):
    body = {"partidas": PARTIDAS if partidas is None else partidas, **extra}
    return client.post(f"/rentas/{renta_id}/cotizacion", json=body, headers=headers)


@pytest.fixture
def solicitada(client, client_h, make_equipo):
    """Una solicitud recién hecha por el cliente de la primera empresa."""
    return pedir(client, client_h, make_equipo()["id"]).json()


@pytest.fixture
def staff(admin_h, ventas_h):
    """Admin y ventas (a los dos les llegan los avisos)."""
    return {"admin": admin_h, "ventas": ventas_h}


# ---------------------------------------------------------------- sugerida


def test_ventas_ve_la_cotizacion_sugerida(client, staff, solicitada) -> None:
    res = client.get(f"/rentas/{solicitada['id']}/cotizacion/sugerida", headers=staff["ventas"])
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["iva_rate"] == 0.16 and cuerpo["anticipo_default_percent"] == 30
    assert cuerpo["valida_horas"] == 24
    assert [p["concepto"] for p in cuerpo["partidas"]] == ["renta", "flete", "operador"]
    assert cuerpo["partidas"][0]["precio_unitario"] == 3400  # la tarifa del equipo


def test_solo_el_personal_cotiza(client, client_h, staff, solicitada) -> None:
    rid = solicitada["id"]
    assert client.get(f"/rentas/{rid}/cotizacion/sugerida", headers=client_h).status_code == 403
    assert cotizar(client, client_h, rid).status_code == 403
    assert client.post(f"/rentas/{rid}/cotizacion", json={"partidas": PARTIDAS}).status_code == 401


# ---------------------------------------------------------------- crear


def test_los_totales_los_calcula_el_servidor(client, staff, solicitada, outbox) -> None:
    res = cotizar(client, staff["ventas"], solicitada["id"])
    assert res.status_code == 201, res.text
    c = res.json()
    assert (
        c["version"] == 1
        and c["estado"] == "vigente"
        and c["creada_por_nombre"] == "Usuario de prueba"
    )
    assert [p["importe"] for p in c["partidas"]] == [27200, 4500]
    assert (c["subtotal"], c["iva"], c["total"]) == (31700, 5072, 36772)
    assert c["anticipo_monto"] == 11031.6  # 30 % del total por defecto
    horas = (datetime.fromisoformat(c["valida_hasta"]) - datetime.now(UTC)).total_seconds() / 3600
    assert 23.9 < horas <= 24
    assert (
        client.get(f"/rentas/{solicitada['id']}", headers=staff["ventas"]).json()["estado"]
        == "cotizada"
    )


def test_avisa_al_cliente_que_su_cotizacion_esta_lista(client, staff, solicitada, outbox) -> None:
    outbox.clear()
    cotizar(client, staff["ventas"], solicitada["id"])
    correo = outbox.to("titular@constructora-prueba.com")[0]
    assert (
        solicitada["folio"] in correo.subject
        and f"/cliente/rentas/{solicitada['id']}" in correo.body
    )


def test_anticipo_y_vigencia_a_medida(client, staff, solicitada) -> None:
    c = cotizar(
        client,
        staff["ventas"],
        solicitada["id"],
        anticipo_monto=20000,
        valida_horas=48,
        notas="Incluye seguro",
    ).json()
    assert c["anticipo_monto"] == 20000 and c["notas"] == "Incluye seguro"
    horas = (datetime.fromisoformat(c["valida_hasta"]) - datetime.now(UTC)).total_seconds() / 3600
    assert 47.9 < horas <= 48


def test_el_anticipo_no_puede_pasar_del_total(client, staff, solicitada) -> None:
    res = cotizar(client, staff["ventas"], solicitada["id"], anticipo_monto=40000)
    assert res.status_code == 409 and "anticipo" in res.json()["detail"]
    assert (
        client.get(f"/rentas/{solicitada['id']}/cotizacion", headers=staff["ventas"]).status_code
        == 404
    )


def test_un_cero_de_anticipo_es_valido(client, staff, solicitada) -> None:
    assert (
        cotizar(client, staff["ventas"], solicitada["id"], anticipo_monto=0).json()[
            "anticipo_monto"
        ]
        == 0
    )


@pytest.mark.parametrize(
    ("partidas", "fragmento"),
    [
        ([], "at least 1"),
        ([{**PARTIDAS[0], "cantidad": 0}], ""),
        ([{**PARTIDAS[0], "cantidad": -1}], ""),
        ([{**PARTIDAS[0], "precio_unitario": -5}], ""),
        ([{**PARTIDAS[0], "precio_unitario": 10.123}], ""),
        ([{**PARTIDAS[0], "descripcion": "ab"}], ""),
        ([{**PARTIDAS[0], "concepto": "regalo"}], ""),
        ([{**PARTIDAS[0], "unidad": "kilo"}], ""),
        ([PARTIDAS[0]] * 31, "at most 30"),
    ],
)
def test_partidas_invalidas(client, staff, solicitada, partidas, fragmento) -> None:
    res = cotizar(client, staff["ventas"], solicitada["id"], partidas=partidas)
    assert res.status_code == 422, res.text
    assert fragmento in res.text


def test_una_partida_de_precio_cero_es_valida_pero_el_redondeo_es_de_centavos(
    client, staff, solicitada
) -> None:
    partidas = [
        {**PARTIDAS[0], "cantidad": 2.5, "precio_unitario": 3400.33},
        {**PARTIDAS[1], "precio_unitario": 0},
    ]
    c = cotizar(client, staff["ventas"], solicitada["id"], partidas=partidas).json()
    assert c["partidas"][0]["importe"] == 8500.83 and c["partidas"][1]["importe"] == 0
    assert c["subtotal"] == 8500.83 and c["iva"] == 1360.13 and c["total"] == 9860.96


def test_una_nueva_version_reemplaza_a_la_anterior(client, staff, solicitada, db) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    nueva = cotizar(
        client, staff["admin"], rid, partidas=[{**PARTIDAS[0], "precio_unitario": 3000}]
    ).json()
    assert nueva["version"] == 2
    actual = client.get(f"/rentas/{rid}/cotizacion", headers=staff["ventas"]).json()
    assert actual["id"] == nueva["id"]
    estados = db.execute(text("SELECT version, estado FROM cotizaciones ORDER BY version")).all()
    assert [(v, e) for v, e in estados] == [(1, "reemplazada"), (2, "vigente")]


def test_no_se_cotiza_lo_que_ya_no_esta_abierto(client, staff, client_h, db, solicitada) -> None:
    rid = solicitada["id"]
    client.post(f"/rentas/{rid}/cancelar", headers=client_h)
    assert cotizar(client, staff["ventas"], rid).status_code == 409
    otra = pedir(client, client_h, solicitada["equipo_id"]).json()
    vencer(db, otra["id"])
    assert cotizar(client, staff["ventas"], otra["id"]).status_code == 409  # la reserva venció


# ---------------------------------------------------------------- ver


def test_cada_quien_ve_solo_lo_suyo(client, staff, client_h, otra_empresa_h, solicitada) -> None:
    rid = solicitada["id"]
    assert (
        client.get(f"/rentas/{rid}/cotizacion", headers=client_h).status_code == 404
    )  # aún no hay
    cotizar(client, staff["ventas"], rid)
    assert client.get(f"/rentas/{rid}/cotizacion", headers=client_h).json()["total"] == 36772
    assert client.get(f"/rentas/{rid}/cotizacion", headers=otra_empresa_h).status_code == 404
    assert client.get(f"/rentas/{rid}/cotizacion").status_code == 401


# ---------------------------------------------------------------- aceptar


def test_aceptar_aparta_el_equipo_tres_horas(
    client, staff, client_h, otra_empresa_h, solicitada, outbox, db
) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    outbox.clear()

    res = client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=client_h)
    assert res.status_code == 200, res.text
    renta = res.json()
    assert renta["estado"] == "apartada"
    horas = (datetime.fromisoformat(renta["vence_en"]) - datetime.now(UTC)).total_seconds() / 3600
    assert 2.9 < horas <= 3

    assert client.get(f"/rentas/{rid}/cotizacion", headers=client_h).json()["estado"] == "aceptada"
    bloqueo = db.query(Bloqueo).filter_by(estado=BloqueoEstado.ACTIVO).one()
    assert bloqueo.tipo == BloqueoTipo.APARTADO
    # El equipo sigue apartado para los demás...
    assert pedir(client, otra_empresa_h, solicitada["equipo_id"]).status_code == 409
    # ...y a todo el personal le avisan.
    for correo in ("admin@chrisco-pruebas.com", "ventas@chrisco-pruebas.com"):
        assert "aceptó la cotización" in outbox.to(correo)[0].subject
        assert f"/admin/rentas/{rid}" in outbox.to(correo)[0].body


def test_no_se_acepta_dos_veces_ni_sin_cotizacion(client, staff, client_h, solicitada) -> None:
    rid = solicitada["id"]
    assert client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=client_h).status_code == 409
    cotizar(client, staff["ventas"], rid)
    assert client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=client_h).status_code == 200
    assert client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=client_h).status_code == 409


def test_solo_el_cliente_dueno_acepta(client, staff, client_h, otra_empresa_h, solicitada) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    assert (
        client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=staff["admin"]).status_code == 403
    )
    assert (
        client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=otra_empresa_h).status_code == 404
    )
    assert client.post(f"/rentas/{rid}/cotizacion/aceptar").status_code == 401


def test_una_cotizacion_vencida_no_se_acepta(client, staff, client_h, db, solicitada) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    db.execute(text("UPDATE cotizaciones SET valida_hasta = now() - interval '1 minute'"))
    db.commit()
    res = client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=client_h)
    assert res.status_code == 409 and "venció" in res.json()["detail"]
    # Al consultar, la cotización y la solicitud quedan vencidas.
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "vencida"
    estado = db.execute(text("SELECT estado FROM cotizaciones")).scalar()
    assert estado == CotizacionEstado.VENCIDA


def test_si_la_reserva_de_20_minutos_vencio_pero_el_equipo_sigue_libre_se_aparta_de_nuevo(
    client, staff, client_h, db, solicitada
) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    vencer(db, rid)  # pasaron los 20 minutos y nadie lo tomó
    res = client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=client_h)
    assert res.status_code == 200 and res.json()["estado"] == "apartada"
    activos = db.query(Bloqueo).filter_by(estado=BloqueoEstado.ACTIVO).all()
    assert len(activos) == 1 and activos[0].tipo == BloqueoTipo.APARTADO


def test_si_otro_cliente_se_adelanto_no_se_puede_aceptar(
    client, staff, client_h, otra_empresa_h, db, solicitada
) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    vencer(db, rid)  # se libera el equipo y otra empresa lo solicita
    assert pedir(client, otra_empresa_h, solicitada["equipo_id"]).status_code == 201

    res = client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=client_h)
    assert res.status_code == 409 and "ya no está disponible" in res.json()["detail"]
    # Todo o nada: la cotización sigue vigente y la renta, cotizada.
    assert client.get(f"/rentas/{rid}/cotizacion", headers=client_h).json()["estado"] == "vigente"
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "cotizada"


# ---------------------------------------------------------------- rechazar


def test_el_cliente_rechaza_la_cotizacion(
    client, staff, client_h, otra_empresa_h, solicitada, db
) -> None:
    rid = solicitada["id"]
    assert client.post(f"/rentas/{rid}/cotizacion/rechazar", headers=client_h).status_code == 409
    cotizar(client, staff["ventas"], rid)
    res = client.post(f"/rentas/{rid}/cotizacion/rechazar", headers=client_h)
    assert res.status_code == 200
    assert (
        res.json()["estado"] == "cancelada"
        and res.json()["motivo_cierre"] == "El cliente rechazó la cotización"
    )
    assert db.execute(text("SELECT estado FROM cotizaciones")).scalar() == "rechazada"
    assert pedir(client, otra_empresa_h, solicitada["equipo_id"]).status_code == 201  # equipo libre


def test_ventas_no_puede_atender_la_solicitud(
    client, staff, client_h, otra_empresa_h, solicitada, outbox
) -> None:
    rid = solicitada["id"]
    outbox.clear()
    res = client.post(
        f"/rentas/{rid}/rechazar",
        json={"motivo": "El equipo está en taller esa semana"},
        headers=staff["ventas"],
    )
    assert res.status_code == 200
    assert (
        res.json()["estado"] == "rechazada"
        and res.json()["motivo_cierre"] == "El equipo está en taller esa semana"
    )
    assert "en taller" in outbox.to("titular@constructora-prueba.com")[0].body
    assert pedir(client, otra_empresa_h, solicitada["equipo_id"]).status_code == 201  # liberado


def test_rechazar_una_solicitud_cotizada_cierra_su_cotizacion(
    client, staff, solicitada, db
) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    client.post(
        f"/rentas/{rid}/rechazar",
        json={"motivo": "Ya no tenemos operadores"},
        headers=staff["admin"],
    )
    assert db.execute(text("SELECT estado FROM cotizaciones")).scalar() == "rechazada"


def test_rechazar_exige_permiso_motivo_y_estado_abierto(
    client, staff, client_h, solicitada
) -> None:
    rid = solicitada["id"]
    assert (
        client.post(
            f"/rentas/{rid}/rechazar", json={"motivo": "No hay equipo"}, headers=client_h
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/rentas/{rid}/rechazar", json={"motivo": "no"}, headers=staff["ventas"]
        ).status_code
        == 422
    )
    cotizar(client, staff["ventas"], rid)
    client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=client_h)
    # Ya aceptada y apartada: no se rechaza desde aquí.
    res = client.post(
        f"/rentas/{rid}/rechazar", json={"motivo": "Cambió el plan"}, headers=staff["ventas"]
    )
    assert res.status_code == 409


def test_cancelar_deja_motivo(client, client_h, solicitada) -> None:
    res = client.post(f"/rentas/{solicitada['id']}/cancelar", headers=client_h).json()
    assert res["estado"] == "cancelada" and res["motivo_cierre"]


# ---------------------------------------------------------------- vencimiento


def test_una_solicitud_cotizada_sin_cotizacion_viva_vence(
    client, staff, client_h, db, solicitada
) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "cotizada"
    db.execute(text("UPDATE cotizaciones SET valida_hasta = now() - interval '1 second'"))
    db.commit()
    assert client.get("/rentas?estado=vencida", headers=client_h).json()["total"] == 1


def test_una_cotizacion_vigente_mantiene_viva_la_solicitud(
    client, staff, client_h, solicitada
) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    assert client.get("/rentas?estado=cotizada", headers=client_h).json()["total"] == 1


def test_el_apartado_vence_a_las_3_horas_y_libera_el_equipo(
    client, staff, client_h, otra_empresa_h, db, solicitada
) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    client.post(f"/rentas/{rid}/cotizacion/aceptar", headers=client_h)
    vencer(db, rid)
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "vencida"
    assert pedir(client, otra_empresa_h, solicitada["equipo_id"]).status_code == 201


# ---------------------------------------------------------------- base de datos


def test_la_base_de_datos_protege_la_cotizacion(client, staff, solicitada, db) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    for sql in (
        "UPDATE cotizaciones SET total = total + 1",  # no cuadra con subtotal + IVA
        "UPDATE cotizaciones SET anticipo_monto = total + 1",
        "UPDATE cotizacion_partidas SET cantidad = 0",
        "UPDATE cotizacion_partidas SET precio_unitario = -1",
    ):
        with pytest.raises(IntegrityError):
            db.execute(text(sql))
        db.rollback()


def test_solo_puede_haber_una_cotizacion_viva_por_renta(client, staff, solicitada, db) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO cotizaciones (id, renta_id, version, estado, subtotal, iva, total, anticipo_monto, valida_hasta) "
                "SELECT gen_random_uuid(), renta_id, 99, 'vigente', 0, 0, 0, 0, now() + interval '1 day' FROM cotizaciones"
            )
        )
    db.rollback()


def test_las_cotizaciones_viejas_no_estorban(client, staff, solicitada, db) -> None:
    rid = solicitada["id"]
    for precio in (3400, 3300, 3200):
        assert (
            cotizar(
                client, staff["ventas"], rid, partidas=[{**PARTIDAS[0], "precio_unitario": precio}]
            ).status_code
            == 201
        )
    assert (
        db.execute(text("SELECT count(*) FROM cotizaciones WHERE estado = 'vigente'")).scalar() == 1
    )
    assert db.execute(text("SELECT count(*) FROM cotizaciones")).scalar() == 3


def test_el_equipo_de_la_cotizacion_no_cambia_el_precio_ya_cotizado(
    client, staff, client_h, admin_h, categoria, solicitada
) -> None:
    rid = solicitada["id"]
    cotizar(client, staff["ventas"], rid)
    equipo_id = solicitada["equipo_id"]
    client.put(
        f"/admin/equipos/{equipo_id}",
        json=equipo_payload(categoria["id"], 1, tarifa_hora=9999),
        headers=staff["admin"],
    )
    assert (
        client.get(f"/rentas/{rid}/cotizacion", headers=client_h).json()["total"] == 36772
    )  # intacto


def test_una_renta_inexistente(client, staff) -> None:
    assert cotizar(client, staff["ventas"], uuid.uuid4()).status_code == 404
    assert (
        client.get(
            f"/rentas/{uuid.uuid4()}/cotizacion/sugerida", headers=staff["ventas"]
        ).status_code
        == 404
    )


def test_el_limite_de_solicitudes_abiertas_no_cuenta_las_cotizadas(
    client, staff, client_h, make_equipo
) -> None:
    primera = pedir(client, client_h, make_equipo()["id"]).json()
    cotizar(client, staff["ventas"], primera["id"])  # sale de «solicitada»
    for _ in range(3):
        assert pedir(client, client_h, make_equipo()["id"]).status_code == 201
    assert pedir(client, client_h, make_equipo()["id"]).status_code == 409
    assert client.get("/rentas?estado=cotizada", headers=client_h).json()["total"] == 1


def test_el_estado_de_la_renta_no_se_pierde_en_el_modelo(db, client, staff, solicitada) -> None:
    cotizar(client, staff["ventas"], solicitada["id"])
    renta = db.get(Renta, uuid.UUID(solicitada["id"]))
    assert renta.estado == RentaEstado.COTIZADA and len(renta.cotizaciones) == 1
    assert renta.cotizaciones[0].partidas[0].orden == 1
    assert (
        timedelta(hours=23)
        < renta.cotizaciones[0].valida_hasta - datetime.now(UTC)
        <= timedelta(hours=24)
    )


def test_dos_empresas_aceptando_a_la_vez_solo_una_aparta_el_equipo(
    client, staff, client_h, otra_empresa_h, db, make_equipo
) -> None:
    """Las dos cotizaciones siguen vigentes pero la reserva de 20 minutos de ambas ya venció:
    quien llega primero a apartar gana; la restricción de la base de datos decide."""
    import threading

    from app.core.errors import Conflict
    from app.db.session import SessionLocal
    from app.services import accounts, cotizaciones

    equipo_id = make_equipo()["id"]
    primera = pedir(client, client_h, equipo_id).json()
    assert cotizar(client, staff["ventas"], primera["id"]).status_code == 201  # a tiempo
    vencer(db, primera["id"])  # pasan los 20 minutos: el equipo queda libre para otros
    segunda = pedir(client, otra_empresa_h, equipo_id).json()
    assert cotizar(client, staff["ventas"], segunda["id"]).status_code == 201
    vencer(db, segunda["id"])

    barrier = threading.Barrier(2)
    resultados: list[str] = []

    def aceptar(renta_id: str, email: str) -> None:
        with SessionLocal() as session:
            renta = session.get(Renta, uuid.UUID(renta_id))
            usuario = accounts.get_by_email(session, email)
            barrier.wait()
            try:
                cotizaciones.accept(session, renta, usuario)
                resultados.append("ok")
            except Conflict:
                resultados.append("conflicto")

    hilos = [
        threading.Thread(target=aceptar, args=(primera["id"], "titular@constructora-prueba.com")),
        threading.Thread(target=aceptar, args=(segunda["id"], "otro@otra-empresa.com")),
    ]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert sorted(resultados) == ["conflicto", "ok"]
    db.expire_all()
    assert db.query(Renta).filter_by(estado=RentaEstado.APARTADA).count() == 1
    assert (
        db.query(Bloqueo).filter_by(estado=BloqueoEstado.ACTIVO, tipo=BloqueoTipo.APARTADO).count()
        == 1
    )


def test_calcular_da_lo_mismo_que_guardar_y_no_guarda_nada(
    client, staff, client_h, solicitada, db
) -> None:
    rid = solicitada["id"]
    cuerpo = {
        "partidas": [{**PARTIDAS[0], "cantidad": 2.5, "precio_unitario": 3400.33}, PARTIDAS[1]],
        "anticipo_monto": 5000,
    }
    calculo = client.post(
        f"/rentas/{rid}/cotizacion/calcular", json=cuerpo, headers=staff["ventas"]
    )
    assert calculo.status_code == 200
    assert db.execute(text("SELECT count(*) FROM cotizaciones")).scalar() == 0
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "solicitada"

    guardada = client.post(f"/rentas/{rid}/cotizacion", json=cuerpo, headers=staff["ventas"]).json()
    c = calculo.json()
    assert c["importes"] == [p["importe"] for p in guardada["partidas"]]
    assert (c["subtotal"], c["iva"], c["total"], c["anticipo_monto"]) == (
        guardada["subtotal"],
        guardada["iva"],
        guardada["total"],
        guardada["anticipo_monto"],
    )


def test_calcular_valida_igual_que_crear(client, staff, client_h, solicitada) -> None:
    rid = solicitada["id"]
    url = f"/rentas/{rid}/cotizacion/calcular"
    assert client.post(url, json={"partidas": []}, headers=staff["ventas"]).status_code == 422
    assert (
        client.post(
            url, json={"partidas": PARTIDAS, "anticipo_monto": 99999}, headers=staff["ventas"]
        ).status_code
        == 409
    )
    assert client.post(url, json={"partidas": PARTIDAS}, headers=client_h).status_code == 403
    assert client.post(url, json={"partidas": PARTIDAS}).status_code == 401
    assert (
        client.post(
            f"/rentas/{uuid.uuid4()}/cotizacion/calcular",
            json={"partidas": PARTIDAS},
            headers=staff["ventas"],
        ).status_code
        == 404
    )

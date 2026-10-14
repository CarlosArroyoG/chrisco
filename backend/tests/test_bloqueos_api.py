import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.models.equipo import Equipo
from app.services import accounts, disponibilidad
from tests.conftest import auth, equipo_payload

NOW = datetime.now(UTC).replace(microsecond=0)


def h(hours: float) -> datetime:
    return NOW + timedelta(hours=hours)


def bloqueo(a: float, b: float, **extra) -> dict:
    return {
        "tipo": "mantenimiento",
        "desde": h(a).isoformat(),
        "hasta": h(b).isoformat(),
        "motivo": "Cambio de aceite",
        **extra,
    }


def ventana(a: float, b: float) -> dict:
    return {"desde": h(a).isoformat(), "hasta": h(b).isoformat()}


def crear(client, headers, equipo_id, a, b, **extra):
    return client.post(
        f"/admin/equipos/{equipo_id}/bloqueos", json=bloqueo(a, b, **extra), headers=headers
    )


# ---------------------------------------------------------------- bloqueos del personal


def test_el_admin_bloquea_y_el_personal_lo_consulta(client, admin_h, ventas_h, make_equipo) -> None:
    equipo = make_equipo()
    res = crear(client, admin_h, equipo["id"], 24, 48)
    assert res.status_code == 201
    creado = res.json()
    assert creado["tipo"] == "mantenimiento" and creado["estado"] == "activo"
    assert (
        creado["motivo"] == "Cambio de aceite"
        and creado["creado_por_nombre"] == "Usuario de prueba"
    )
    assert creado["vence_en"] is None

    for headers in (admin_h, ventas_h):
        listado = client.get(f"/admin/equipos/{equipo['id']}/bloqueos", headers=headers).json()
        assert [b["id"] for b in listado] == [creado["id"]]


def test_solo_el_admin_crea_y_libera_bloqueos(
    client, admin_h, ventas_h, client_h, make_equipo
) -> None:
    equipo = make_equipo()
    for headers in (ventas_h, client_h):
        assert crear(client, headers, equipo["id"], 1, 2).status_code == 403
    assert (
        client.post(f"/admin/equipos/{equipo['id']}/bloqueos", json=bloqueo(1, 2)).status_code
        == 401
    )
    creado = crear(client, admin_h, equipo["id"], 1, 2).json()
    assert (
        client.post(f"/admin/bloqueos/{creado['id']}/liberar", headers=ventas_h).status_code == 403
    )
    assert (
        client.get(f"/admin/equipos/{equipo['id']}/bloqueos", headers=client_h).status_code == 403
    )


def test_un_bloqueo_que_se_traslapa_se_rechaza(client, admin_h, make_equipo) -> None:
    equipo = make_equipo()
    crear(client, admin_h, equipo["id"], 10, 20)
    res = crear(client, admin_h, equipo["id"], 15, 25)
    assert res.status_code == 409 and "no está disponible" in res.json()["detail"]
    assert crear(client, admin_h, equipo["id"], 20, 30).status_code == 201  # contiguo


@pytest.mark.parametrize(
    ("cambio", "fragmento"),
    [
        ({"hasta": h(1).isoformat(), "desde": h(2).isoformat()}, "posterior"),
        ({"hasta": h(1).isoformat(), "desde": h(1).isoformat()}, "posterior"),
        ({"desde": h(-10).isoformat(), "hasta": h(-5).isoformat()}, "futuro"),
        ({"desde": h(0).isoformat(), "hasta": h(24 * 400).isoformat()}, "366"),
        ({"desde": "2030-01-01T10:00:00", "hasta": "2030-01-02T10:00:00"}, "timezone"),  # sin zona
        ({"motivo": "ab"}, ""),
        ({"motivo": ""}, ""),
        ({"tipo": "renta"}, ""),
        ({"tipo": "solicitud"}, ""),
    ],
)
def test_validaciones_del_bloqueo(client, admin_h, make_equipo, cambio, fragmento) -> None:
    equipo = make_equipo()
    body = {**bloqueo(1, 2), **cambio}
    res = client.post(f"/admin/equipos/{equipo['id']}/bloqueos", json=body, headers=admin_h)
    assert res.status_code == 422, res.text
    assert fragmento in res.text


def test_equipo_inexistente(client, admin_h) -> None:
    assert crear(client, admin_h, uuid.uuid4(), 1, 2).status_code == 404
    assert client.get(f"/admin/equipos/{uuid.uuid4()}/bloqueos", headers=admin_h).status_code == 404


def test_liberar_un_bloqueo_del_personal(client, admin_h, make_equipo) -> None:
    equipo = make_equipo()
    creado = crear(client, admin_h, equipo["id"], 1, 5).json()
    assert (
        client.post(f"/admin/bloqueos/{creado['id']}/liberar", headers=admin_h).status_code == 204
    )
    assert client.get(f"/admin/equipos/{equipo['id']}/bloqueos", headers=admin_h).json() == []
    assert (
        client.post(f"/admin/bloqueos/{creado['id']}/liberar", headers=admin_h).status_code == 409
    )
    assert crear(client, admin_h, equipo["id"], 1, 5).status_code == 201  # ya quedó libre
    assert (
        client.post(f"/admin/bloqueos/{uuid.uuid4()}/liberar", headers=admin_h).status_code == 404
    )


def test_las_rentas_no_se_liberan_desde_aqui(client, admin_h, db, make_equipo) -> None:
    equipo = db.get(Equipo, uuid.UUID(make_equipo()["id"]))
    admin = accounts.get_by_email(db, "admin@chrisco-pruebas.com")
    hold = disponibilidad.place_hold(db, equipo, h(1), h(2), admin)
    res = client.post(f"/admin/bloqueos/{hold.id}/liberar", headers=admin_h)
    assert res.status_code == 409 and "renta" in res.json()["detail"]


def test_el_listado_de_bloqueos_solo_trae_los_vigentes_o_futuros(
    client, admin_h, db, make_equipo
) -> None:
    equipo = db.get(Equipo, uuid.UUID(make_equipo()["id"]))
    admin = accounts.get_by_email(db, "admin@chrisco-pruebas.com")
    disponibilidad.block(db, equipo, "mantenimiento", h(-10), h(-5), "ya pasó", admin)
    disponibilidad.block(db, equipo, "mantenimiento", h(-1), h(1), "en curso", admin)
    disponibilidad.block(db, equipo, "manual", h(5), h(6), "futuro", admin)
    motivos = [
        b["motivo"]
        for b in client.get(f"/admin/equipos/{equipo.id}/bloqueos", headers=admin_h).json()
    ]
    assert motivos == ["en curso", "futuro"]


# ---------------------------------------------------------------- estado actual en la lista


def test_la_lista_muestra_la_situacion_actual_de_cada_equipo(
    client, admin_h, ventas_h, categoria, make_equipo
) -> None:
    libre, en_servicio, con_futuro, mantenimiento = (make_equipo() for _ in range(4))
    crear(client, admin_h, en_servicio["id"], -1, 5)
    crear(client, admin_h, con_futuro["id"], 24, 30)
    body = equipo_payload(categoria["id"], 4, status="mantenimiento")
    client.put(f"/admin/equipos/{mantenimiento['id']}", json=body, headers=admin_h)

    for headers in (admin_h, ventas_h):
        items = client.get("/admin/equipos", headers=headers).json()["items"]
        estados = {e["codigo"]: e["estado_actual"] for e in items}
        assert estados == {
            "EQ-001": "libre",
            "EQ-002": "mantenimiento",
            "EQ-003": "libre",  # su bloqueo es mañana
            "EQ-004": "mantenimiento",
        }
    detalle = client.get(f"/admin/equipos/{en_servicio['id']}", headers=admin_h).json()
    assert detalle["estado_actual"] == "mantenimiento"
    assert libre["estado_actual"] == "libre"  # también al crear


def test_un_equipo_dado_de_baja_figura_como_baja(client, admin_h, categoria, make_equipo) -> None:
    equipo = make_equipo()
    body = equipo_payload(categoria["id"], 1, status="baja")
    assert (
        client.put(f"/admin/equipos/{equipo['id']}", json=body, headers=admin_h).json()[
            "estado_actual"
        ]
        == "baja"
    )


# ---------------------------------------------------------------- disponibilidad para clientes


def test_el_catalogo_sin_periodo_no_inventa_disponibilidad(client, client_h, make_equipo) -> None:
    make_equipo()
    assert client.get("/equipos", headers=client_h).json()["items"][0]["disponible"] is None


def test_el_catalogo_marca_que_equipos_estan_libres_en_un_periodo(
    client, client_h, admin_h, make_equipo
) -> None:
    libre, ocupado = make_equipo(), make_equipo()
    crear(client, admin_h, ocupado["id"], 10, 20)

    def listar(a, b, **extra):
        params = {**ventana(a, b), **extra}
        return client.get("/equipos", params=params, headers=client_h).json()

    solapado = listar(15, 25)
    assert {e["codigo"]: e["disponible"] for e in solapado["items"]} == {
        "EQ-001": True,
        "EQ-002": False,
    }
    contiguo = listar(20, 30)
    assert all(e["disponible"] for e in contiguo["items"])

    solo = listar(15, 25, solo_disponibles="true")
    assert solo["total"] == 1 and [e["id"] for e in solo["items"]] == [libre["id"]]


def test_solo_disponibles_pagina_bien(client, client_h, admin_h, make_equipo) -> None:
    equipos = [make_equipo() for _ in range(4)]
    crear(client, admin_h, equipos[0]["id"], 10, 20)
    crear(client, admin_h, equipos[2]["id"], 10, 20)
    params = {**ventana(12, 14), "solo_disponibles": "true", "limit": 1}
    pagina = client.get("/equipos", params=params, headers=client_h).json()
    assert pagina["total"] == 2 and len(pagina["items"]) == 1
    siguiente = client.get("/equipos", params={**params, "offset": 1}, headers=client_h).json()
    assert {pagina["items"][0]["id"], siguiente["items"][0]["id"]} == {
        equipos[1]["id"],
        equipos[3]["id"],
    }


def test_una_reserva_provisional_vencida_no_oculta_el_equipo(
    client, client_h, admin_h, db, make_equipo
) -> None:
    equipo = db.get(Equipo, uuid.UUID(make_equipo()["id"]))
    admin = accounts.get_by_email(db, "admin@chrisco-pruebas.com")
    hold = disponibilidad.place_hold(db, equipo, h(1), h(5), admin)
    params = {**ventana(2, 3), "solo_disponibles": "true"}
    assert client.get("/equipos", params=params, headers=client_h).json()["total"] == 0
    db.execute(
        text("UPDATE bloqueos SET vence_en = now() - interval '1 minute' WHERE id = :i"),
        {"i": hold.id},
    )
    db.commit()
    assert client.get("/equipos", params=params, headers=client_h).json()["total"] == 1


@pytest.mark.parametrize(
    "params",
    [
        {"desde": "2030-01-01T10:00:00+00:00"},  # falta hasta
        {"hasta": "2030-01-01T10:00:00+00:00"},  # falta desde
        {"desde": "2030-01-02T10:00:00+00:00", "hasta": "2030-01-01T10:00:00+00:00"},
        {"desde": "2030-01-01T10:00:00", "hasta": "2030-01-02T10:00:00"},  # sin zona horaria
        {"solo_disponibles": "true"},  # sin periodo
    ],
)
def test_consultas_de_periodo_invalidas(client, client_h, make_equipo, params) -> None:
    make_equipo()
    assert client.get("/equipos", params=params, headers=client_h).status_code == 422


def test_disponibilidad_de_un_equipo(client, client_h, admin_h, make_equipo) -> None:
    equipo = make_equipo()
    crear(client, admin_h, equipo["id"], 10, 20, motivo="Reparación del motor")
    url = f"/equipos/{equipo['id']}/disponibilidad"

    ocupado = client.get(url, params=ventana(15, 25), headers=client_h).json()
    assert ocupado["disponible"] is False
    assert len(ocupado["ocupado"]) == 1
    # Un cliente no sabe por qué está ocupado: solo cuándo.
    assert set(ocupado["ocupado"][0]) == {"desde", "hasta"}
    assert "motor" not in str(ocupado) and "mantenimiento" not in str(ocupado)

    libre = client.get(url, params=ventana(20, 30), headers=client_h).json()
    assert libre["disponible"] is True and libre["ocupado"] == []


def test_disponibilidad_requiere_periodo_y_acceso(
    client, client_h, make_equipo, register, verify_email, login
) -> None:
    equipo = make_equipo()
    url = f"/equipos/{equipo['id']}/disponibilidad"
    assert client.get(url, headers=client_h).status_code == 422
    assert client.get(url, params={"desde": h(1).isoformat()}, headers=client_h).status_code == 422
    assert client.get(url, params=ventana(1, 2)).status_code == 401
    assert (
        client.get(
            f"/equipos/{uuid.uuid4()}/disponibilidad", params=ventana(1, 2), headers=client_h
        ).status_code
        == 404
    )

    register(rfc="OTR020202XY9", email="otro@otra-empresa.com")
    verify_email("otro@otra-empresa.com")
    pendiente = auth(login("otro@otra-empresa.com"))
    assert client.get(url, params=ventana(1, 2), headers=pendiente).status_code == 403


def test_un_equipo_fuera_de_catalogo_no_tiene_disponibilidad_publica(
    client, client_h, admin_h, categoria, make_equipo
) -> None:
    equipo = make_equipo()
    client.put(
        f"/admin/equipos/{equipo['id']}",
        json=equipo_payload(categoria["id"], 1, status="mantenimiento"),
        headers=admin_h,
    )
    res = client.get(
        f"/equipos/{equipo['id']}/disponibilidad", params=ventana(1, 2), headers=client_h
    )
    assert res.status_code == 404

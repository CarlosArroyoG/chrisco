"""El operador de CHRISCO ve y mueve solo lo que entrega y recibe."""

import uuid
from decimal import Decimal

import pytest

from app.models.equipo import Equipo
from app.models.user import Role
from tests.conftest import auth
from tests.rentas_helpers import apartar
from tests.test_cumplimiento import completar
from tests.test_movimientos import mover


@pytest.fixture
def staff(admin_h, ventas_h):
    return {"admin": admin_h, "ventas": ventas_h}


@pytest.fixture
def operador_h(make_user, login):
    make_user("operador@chrisco-pruebas.com", Role.OPERADOR)
    return auth(login("operador@chrisco-pruebas.com"))


@pytest.fixture
def confirmada(client, client_h, staff, make_equipo, db):
    equipo = make_equipo()
    db.query(Equipo).filter_by(id=uuid.UUID(equipo["id"])).update({"horometro": Decimal(0)})
    db.commit()
    renta = apartar(client, client_h, staff["ventas"], equipo["id"], transporte="recoge")
    completar(client, client_h, staff, renta["id"])
    return renta


def test_el_operador_entrega_y_recibe(client, client_h, operador_h, confirmada) -> None:
    rid = confirmada["id"]
    assert mover(client, operador_h, rid, "salida", 10).status_code == 201
    assert client.get(f"/rentas/{rid}", headers=operador_h).json()["estado"] == "en_renta"
    res = mover(client, operador_h, rid, "regreso", 18)
    assert res.status_code == 201 and res.json()["registrado_por_nombre"] == "Usuario de prueba"
    # Tras el regreso todavía ve la renta (y las horas), no se le "pierde" de pronto.
    assert client.get(f"/rentas/{rid}", headers=operador_h).json()["estado"] in (
        "devuelta",
        "cerrada",
    )
    listado = client.get(f"/rentas/{rid}/movimientos", headers=operador_h)
    assert listado.status_code == 200 and listado.json()["horas_usadas"] == 8


def test_solo_ve_las_rentas_de_entrega_y_recepcion(
    client, client_h, staff, operador_h, confirmada, make_equipo
) -> None:
    apartada = apartar(client, client_h, staff["ventas"], make_equipo()["id"], transporte="recoge")
    ids = [r["id"] for r in client.get("/rentas", headers=operador_h).json()["items"]]
    assert ids == [confirmada["id"]]
    assert client.get(f"/rentas/{apartada['id']}", headers=operador_h).status_code == 404
    assert (
        client.get(f"/rentas/{apartada['id']}/movimientos", headers=operador_h).status_code == 404
    )
    assert mover(client, operador_h, apartada["id"], "salida", 1).status_code == 404


def test_no_accede_a_dinero_ni_a_documentos_ni_a_la_administracion(
    client, operador_h, confirmada
) -> None:
    rid = confirmada["id"]
    for url in (
        f"/rentas/{rid}/cumplimiento",
        f"/rentas/{rid}/cotizacion",
        f"/rentas/{rid}/whatsapp",
        "/admin/cobranza",
        "/admin/personal",
        "/admin/mantenimiento",
        "/admin/equipos",
        "/admin/empresas",
    ):
        assert client.get(url, headers=operador_h).status_code == 403, url
    assert client.post(f"/rentas/{rid}/cancelar", headers=operador_h).status_code == 403


def test_la_foto_del_tablero_la_ve_el_operador(client, operador_h, confirmada) -> None:
    rid = confirmada["id"]
    mov = mover(client, operador_h, rid, "salida", 5).json()
    res = client.get(f"/rentas/{rid}/movimientos/{mov['id']}/foto", headers=operador_h)
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"

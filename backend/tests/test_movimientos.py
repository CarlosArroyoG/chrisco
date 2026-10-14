"""Salida y regreso del equipo: horómetro, foto, estados de la renta y cierre."""

import threading
import uuid
from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.models.equipo import Equipo, EquipoStatus
from app.models.renta import Renta, RentaEstado
from app.schemas.movimiento import MovimientoIn
from app.services import accounts, movimientos
from app.services.storage import get_storage
from tests.rentas_helpers import ANTICIPO, TOTAL, apartar, pedir
from tests.test_cumplimiento import completar, pagar, png, revisar_pago


@pytest.fixture
def staff(admin_h, ventas_h):
    return {"admin": admin_h, "ventas": ventas_h}


@pytest.fixture
def confirmada(client, client_h, staff, make_equipo, db):
    """Renta confirmada (requisitos cumplidos y anticipo recibido), lista para entregar."""
    equipo = make_equipo()
    db.query(Equipo).filter_by(id=uuid.UUID(equipo["id"])).update({"horometro": Decimal(0)})
    db.commit()
    renta = apartar(client, client_h, staff["ventas"], equipo["id"], transporte="recoge")
    completar(client, client_h, staff, renta["id"])
    return renta


def mover(client, headers, renta_id, tipo, horometro, foto=None, notas=None):
    campos = {"tipo": tipo, "horometro": str(horometro)}
    if notas:
        campos["notas"] = notas
    return client.post(
        f"/rentas/{renta_id}/movimientos",
        data=campos,
        files={"foto": ("tablero.png", png() if foto is None else foto, "image/png")},
        headers=headers,
    )


def estado(client, headers, renta_id) -> str:
    return client.get(f"/rentas/{renta_id}", headers=headers).json()["estado"]


def horometro_de(db, equipo_id) -> Decimal:
    db.expire_all()
    return db.get(Equipo, uuid.UUID(equipo_id)).horometro


def test_la_salida_pasa_la_renta_a_en_renta(client, client_h, staff, confirmada, db) -> None:
    rid = confirmada["id"]
    res = mover(client, staff["ventas"], rid, "salida", 120.5, notas="Sale con tanque lleno")
    assert res.status_code == 201, res.text
    mov = res.json()
    assert mov["tipo"] == "salida" and mov["horometro"] == 120.5
    assert mov["notas"] == "Sale con tanque lleno" and mov["registrado_por_nombre"]
    assert estado(client, client_h, rid) == "en_renta"
    assert horometro_de(db, confirmada["equipo_id"]) == Decimal("120.5")

    listado = client.get(f"/rentas/{rid}/movimientos", headers=client_h).json()
    assert [m["tipo"] for m in listado["movimientos"]] == ["salida"]
    assert listado["horas_usadas"] is None


def test_el_regreso_registra_las_horas_y_libera_el_equipo(
    client, client_h, otra_empresa_h, staff, confirmada, db
) -> None:
    rid = confirmada["id"]
    mover(client, staff["ventas"], rid, "salida", 100)
    res = mover(client, staff["admin"], rid, "regreso", 108.5)
    assert res.status_code == 201, res.text
    assert estado(client, client_h, rid) == "devuelta"
    assert horometro_de(db, confirmada["equipo_id"]) == Decimal("108.5")
    listado = client.get(f"/rentas/{rid}/movimientos", headers=staff["ventas"]).json()
    assert listado["horas_usadas"] == 8.5
    # El equipo ya no está apartado para ese periodo: otra empresa puede pedirlo.
    assert pedir(client, otra_empresa_h, confirmada["equipo_id"]).status_code == 201


def test_las_fotos_son_privadas(client, client_h, otra_empresa_h, staff, confirmada) -> None:
    rid = confirmada["id"]
    mov = mover(client, staff["ventas"], rid, "salida", 10).json()
    url = f"/rentas/{rid}/movimientos/{mov['id']}/foto"
    for headers in (client_h, staff["ventas"]):
        res = client.get(url, headers=headers)
        assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
        assert res.headers["cache-control"] == "no-store"
    assert client.get(url, headers=otra_empresa_h).status_code == 404
    assert client.get(url).status_code == 401
    assert (
        client.get(f"/rentas/{rid}/movimientos/{uuid.uuid4()}/foto", headers=client_h).status_code
        == 404
    )


def test_solo_se_entrega_una_renta_confirmada(client, client_h, staff, make_equipo) -> None:
    solicitada = pedir(client, client_h, make_equipo()["id"]).json()
    assert mover(client, staff["ventas"], solicitada["id"], "salida", 1).status_code == 409
    apartada = apartar(client, client_h, staff["ventas"], make_equipo()["id"], transporte="recoge")
    assert mover(client, staff["ventas"], apartada["id"], "salida", 1).status_code == 409
    assert estado(client, client_h, apartada["id"]) == "apartada"


def test_no_hay_regreso_sin_salida_ni_dos_salidas(client, client_h, staff, confirmada) -> None:
    rid = confirmada["id"]
    assert mover(client, staff["ventas"], rid, "regreso", 5).status_code == 409
    assert mover(client, staff["ventas"], rid, "salida", 5).status_code == 201
    assert mover(client, staff["ventas"], rid, "salida", 6).status_code == 409
    assert mover(client, staff["ventas"], rid, "regreso", 9).status_code == 201
    assert mover(client, staff["ventas"], rid, "regreso", 10).status_code == 409


def test_el_horometro_no_retrocede(client, client_h, staff, confirmada, db) -> None:
    rid = confirmada["id"]
    db.query(Equipo).filter_by(id=uuid.UUID(confirmada["equipo_id"])).update(
        {"horometro": Decimal("500")}
    )
    db.commit()
    res = mover(client, staff["ventas"], rid, "salida", 499.9)
    assert res.status_code == 422 and "último registrado (500" in res.json()["detail"]
    assert estado(client, client_h, rid) == "confirmada"

    mover(client, staff["ventas"], rid, "salida", 500)
    res = mover(client, staff["ventas"], rid, "regreso", 499)
    assert res.status_code == 422 and "menor al de la salida" in res.json()["detail"]
    assert estado(client, client_h, rid) == "en_renta"


@pytest.mark.parametrize(
    ("campos", "fragmento"),
    [
        ({"horometro": "-1"}, ""),
        ({"horometro": "abc"}, ""),
        ({"horometro": "10.55"}, ""),
        ({"tipo": "otro"}, ""),
    ],
)
def test_datos_invalidos(client, staff, confirmada, campos, fragmento) -> None:
    datos = {"tipo": "salida", "horometro": "10", **campos}
    res = client.post(
        f"/rentas/{confirmada['id']}/movimientos",
        data=datos,
        files={"foto": ("t.png", png(), "image/png")},
        headers=staff["ventas"],
    )
    assert res.status_code == 422


def test_la_foto_es_obligatoria_y_debe_ser_una_imagen(client, client_h, staff, confirmada) -> None:
    rid = confirmada["id"]
    sin_foto = client.post(
        f"/rentas/{rid}/movimientos",
        data={"tipo": "salida", "horometro": "10"},
        headers=staff["ventas"],
    )
    assert sin_foto.status_code == 422
    res = mover(client, staff["ventas"], rid, "salida", 10, foto=b"no soy una imagen")
    assert res.status_code == 422
    assert estado(client, client_h, rid) == "confirmada"  # nada cambió


def test_un_equipo_en_mantenimiento_no_sale(client, client_h, staff, confirmada, db) -> None:
    db.query(Equipo).filter_by(id=uuid.UUID(confirmada["equipo_id"])).update(
        {"status": EquipoStatus.MANTENIMIENTO}
    )
    db.commit()
    res = mover(client, staff["ventas"], confirmada["id"], "salida", 10)
    assert res.status_code == 409 and "no está activo" in res.json()["detail"]


def test_permisos(client, client_h, otra_empresa_h, staff, confirmada) -> None:
    rid = confirmada["id"]
    assert mover(client, client_h, rid, "salida", 1).status_code == 403
    assert mover(client, otra_empresa_h, rid, "salida", 1).status_code == 403
    assert client.get(f"/rentas/{rid}/movimientos", headers=otra_empresa_h).status_code == 404
    assert client.get(f"/rentas/{rid}/movimientos").status_code == 401


# ---------------------------------------------------------------- cierre


def test_devuelta_y_pagada_por_completo_se_cierra(client, client_h, staff, confirmada) -> None:
    rid = confirmada["id"]
    pago = pagar(client, client_h, rid, TOTAL - ANTICIPO).json()
    revisar_pago(client, staff["ventas"], rid, pago["id"])
    mover(client, staff["ventas"], rid, "salida", 0)
    mover(client, staff["ventas"], rid, "regreso", 10)
    assert estado(client, client_h, rid) == "cerrada"


def test_devuelta_con_saldo_se_cierra_al_confirmar_el_ultimo_pago(
    client, client_h, staff, confirmada
) -> None:
    rid = confirmada["id"]
    mover(client, staff["ventas"], rid, "salida", 0)
    mover(client, staff["ventas"], rid, "regreso", 10)
    assert estado(client, client_h, rid) == "devuelta"

    pago = pagar(client, client_h, rid, TOTAL - ANTICIPO).json()
    assert estado(client, client_h, rid) == "devuelta"  # reportado, aún sin confirmar
    revisar_pago(client, staff["ventas"], rid, pago["id"])
    assert estado(client, client_h, rid) == "cerrada"


def test_un_pago_parcial_no_cierra(client, client_h, staff, confirmada) -> None:
    rid = confirmada["id"]
    mover(client, staff["ventas"], rid, "salida", 0)
    mover(client, staff["ventas"], rid, "regreso", 10)
    revisar_pago(client, staff["ventas"], rid, pagar(client, client_h, rid, 1000).json()["id"])
    assert estado(client, client_h, rid) == "devuelta"


# ---------------------------------------------------------------- concurrencia


def test_dos_salidas_simultaneas_solo_registran_una(client, staff, confirmada, db) -> None:
    rid = uuid.UUID(confirmada["id"])
    barrier = threading.Barrier(2)
    resultados: list[str] = []

    def entregar() -> None:
        with SessionLocal() as session:
            renta = session.get(Renta, rid)
            persona = accounts.get_by_email(session, "ventas@chrisco-pruebas.com")
            barrier.wait()
            try:
                movimientos.register(
                    session,
                    get_storage(),
                    renta,
                    persona,
                    MovimientoIn(tipo="salida", horometro=Decimal("5")),
                    png(),
                )
                resultados.append("ok")
            except Exception as exc:
                resultados.append(type(exc).__name__)

    hilos = [threading.Thread(target=entregar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(resultados) == ["Conflict", "ok"]
    db.expire_all()
    assert db.get(Renta, rid).estado == RentaEstado.EN_RENTA
    assert len(db.get(Renta, rid).movimientos) == 1

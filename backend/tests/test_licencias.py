"""Licencia federal del operador de la empresa cliente: revisión manual con número y vigencia."""

from datetime import UTC, datetime, timedelta

import pytest

from tests.rentas_helpers import apartar
from tests.test_cumplimiento import (
    cumplimiento_de,
    pagar,
    png,
    revisar_doc,
    revisar_pago,
    situaciones,
    subir,
)


@pytest.fixture
def staff(admin_h, ventas_h):
    return {"admin": admin_h, "ventas": ventas_h}


@pytest.fixture
def con_licencia(client, client_h, staff, make_equipo):
    """Renta apartada con operador de la empresa cliente: exige la licencia federal."""
    return apartar(
        client,
        client_h,
        staff["ventas"],
        make_equipo()["id"],
        operador_modo="cliente",
        transporte="recoge",
    )


def aprobar(client, headers, renta_id, doc_id, **datos):
    return client.post(
        f"/rentas/{renta_id}/documentos/{doc_id}/revisar",
        json={"aprobado": True, **datos},
        headers=headers,
    )


def dia(delta: int) -> str:
    return (datetime.now(UTC) + timedelta(days=delta)).date().isoformat()


def test_la_licencia_es_un_requisito_cuando_opera_el_cliente(
    client, client_h, con_licencia
) -> None:
    c = cumplimiento_de(client, client_h, con_licencia["id"])
    assert situaciones(c)["licencia_federal"] == "pendiente"
    assert "QR" not in str(c["checklist"])  # la verificación es manual


def test_aprobar_una_licencia_registra_numero_y_vigencia(
    client, client_h, staff, con_licencia
) -> None:
    rid = con_licencia["id"]
    doc = subir(client, client_h, rid, "licencia_federal", png(), "licencia.png").json()
    res = aprobar(
        client, staff["ventas"], rid, doc["id"], numero="LF-123456", vigente_hasta=dia(365)
    )
    assert res.status_code == 200, res.text
    assert situaciones(res.json())["licencia_federal"] == "cumplido"
    guardado = res.json()["documentos"][0]
    assert guardado["numero"] == "LF-123456" and guardado["vigente_hasta"] == dia(365)


@pytest.mark.parametrize(
    "datos",
    [{}, {"numero": "LF-123456"}, {"vigente_hasta": "2099-01-01"}],
    ids=["nada", "sin-vigencia", "sin-numero"],
)
def test_la_licencia_no_se_aprueba_sin_sus_datos(
    client, client_h, staff, con_licencia, datos
) -> None:
    rid = con_licencia["id"]
    doc = subir(client, client_h, rid, "licencia_federal").json()
    res = aprobar(client, staff["ventas"], rid, doc["id"], **datos)
    assert res.status_code == 422 and "número y su vigencia" in res.json()["detail"]
    assert situaciones(cumplimiento_de(client, client_h, rid))["licencia_federal"] == "en_revision"


def test_una_licencia_que_vence_antes_del_fin_de_la_renta_no_se_aprueba(
    client, client_h, staff, con_licencia
) -> None:
    rid = con_licencia["id"]
    doc = subir(client, client_h, rid, "licencia_federal").json()
    res = aprobar(client, staff["ventas"], rid, doc["id"], numero="LF-1234", vigente_hasta=dia(-1))
    assert res.status_code == 422 and "antes de que termine la" in res.json()["detail"]
    # Se rechaza con motivo y para eso no hacen falta datos de licencia.
    assert (
        revisar_doc(client, staff["ventas"], rid, doc["id"], False, "Licencia vencida").status_code
        == 200
    )


def test_otros_documentos_no_piden_datos_de_licencia(client, client_h, staff, con_licencia) -> None:
    rid = con_licencia["id"]
    doc = subir(client, client_h, rid, "contrato").json()
    assert revisar_doc(client, staff["ventas"], rid, doc["id"]).status_code == 200
    assert cumplimiento_de(client, client_h, rid)["documentos"][0]["numero"] is None


def test_con_la_licencia_aprobada_y_todo_lo_demas_la_renta_se_confirma(
    client, client_h, staff, con_licencia
) -> None:
    rid = con_licencia["id"]
    for requisito in ("contrato", "poliza"):
        doc = subir(client, client_h, rid, requisito).json()
        revisar_doc(client, staff["ventas"], rid, doc["id"])
    revisar_pago(client, staff["ventas"], rid, pagar(client, client_h, rid).json()["id"])
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "apartada"
    doc = subir(client, client_h, rid, "licencia_federal").json()
    aprobar(client, staff["ventas"], rid, doc["id"], numero="LF-777", vigente_hasta=dia(365))
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "confirmada"

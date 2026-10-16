"""Requisitos del apartado: documentos, condiciones, pagos y confirmación automática."""

import io
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import text

from app.core.clock import today
from app.core.config import get_settings
from app.core.errors import Conflict
from app.db.session import SessionLocal
from app.models.bloqueo import Bloqueo, BloqueoEstado, BloqueoTipo
from app.models.renta import Renta, RentaEstado
from app.schemas.cumplimiento import RevisionIn
from app.services import accounts, cumplimiento
from tests.conftest import PDF, auth, equipo_payload
from tests.rentas_helpers import ANTICIPO, TOTAL, apartar, cotizar, pedir, vencer


@pytest.fixture
def staff(admin_h, ventas_h):
    return {"admin": admin_h, "ventas": ventas_h}


@pytest.fixture
def apartada(client, client_h, staff, make_equipo):
    """Renta apartada con operador de CHRISCO que el cliente recoge: contrato, póliza y anticipo."""
    return apartar(client, client_h, staff["ventas"], make_equipo()["id"], transporte="recoge")


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 120, 200)).save(out, format="PNG")
    return out.getvalue()


def subir(client, headers, renta_id, requisito="contrato", data=PDF, name="doc.pdf"):
    return client.post(
        f"/rentas/{renta_id}/documentos",
        data={"requisito": requisito},
        files={"archivo": (name, data, "application/octet-stream")},
        headers=headers,
    )


def pagar(client, headers, renta_id, monto=ANTICIPO, fecha=None, referencia="SPEI123", data=PDF):
    fecha = fecha or today().isoformat()
    campos = {"monto": str(monto), "fecha_pago": fecha}
    if referencia:
        campos["referencia"] = referencia
    return client.post(
        f"/rentas/{renta_id}/pagos",
        data=campos,
        files={"comprobante": ("comprobante.pdf", data, "application/pdf")},
        headers=headers,
    )


def cumplimiento_de(client, headers, renta_id) -> dict:
    return client.get(f"/rentas/{renta_id}/cumplimiento", headers=headers).json()


def situaciones(c: dict) -> dict[str, str]:
    return {i["codigo"]: i["situacion"] for i in c["checklist"]}


def revisar_doc(client, headers, renta_id, doc_id, aprobado=True, nota=None):
    return client.post(
        f"/rentas/{renta_id}/documentos/{doc_id}/revisar",
        json={"aprobado": aprobado, "nota": nota},
        headers=headers,
    )


def revisar_pago(client, headers, renta_id, pago_id, aprobado=True, nota=None):
    return client.post(
        f"/rentas/{renta_id}/pagos/{pago_id}/revisar",
        json={"aprobado": aprobado, "nota": nota},
        headers=headers,
    )


def completar(client, client_h, staff, renta_id, monto=ANTICIPO):
    """Entrega y aprueba todo: contrato, póliza y el anticipo."""
    for requisito in ("contrato", "poliza"):
        doc = subir(client, client_h, renta_id, requisito).json()
        assert revisar_doc(client, staff["ventas"], renta_id, doc["id"]).status_code == 200
    pago = pagar(client, client_h, renta_id, monto).json()
    return revisar_pago(client, staff["ventas"], renta_id, pago["id"])


# ---------------------------------------------------------------- lista de requisitos


def test_la_lista_inicial_de_requisitos(client, client_h, apartada) -> None:
    c = cumplimiento_de(client, client_h, apartada["id"])
    assert situaciones(c) == {
        "contrato": "pendiente",
        "poliza": "pendiente",
        "anticipo": "pendiente",
    }
    assert c["total"] == TOTAL and c["anticipo_requerido"] == ANTICIPO
    assert c["pagado"] == 0 and c["saldo"] == TOTAL and c["confirmada"] is False
    assert c["documentos"] == [] and c["pagos"] == []
    # Los cargos (operador, flete) se cotizan: no son requisitos que cumplir.
    assert "operador_chrisco" not in situaciones(c)


def test_el_cumplimiento_solo_lo_ven_la_empresa_y_el_personal(
    client, client_h, otra_empresa_h, staff, apartada
) -> None:
    rid = apartada["id"]
    assert client.get(f"/rentas/{rid}/cumplimiento", headers=staff["ventas"]).status_code == 200
    assert client.get(f"/rentas/{rid}/cumplimiento", headers=otra_empresa_h).status_code == 404
    assert client.get(f"/rentas/{rid}/cumplimiento").status_code == 401


# ---------------------------------------------------------------- documentos


def test_el_cliente_sube_un_documento(client, client_h, apartada) -> None:
    res = subir(client, client_h, apartada["id"], "contrato")
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["requisito"] == "contrato" and doc["estado"] == "pendiente"
    assert doc["filename"] == "doc.pdf" and doc["subido_por_nombre"] == "Titular Prueba"
    assert (
        situaciones(cumplimiento_de(client, client_h, apartada["id"]))["contrato"] == "en_revision"
    )


def test_tambien_se_aceptan_fotos_y_se_vuelven_a_codificar(client, client_h, apartada) -> None:
    doc = subir(client, client_h, apartada["id"], "poliza", png(), "foto.png").json()
    res = client.get(f"/rentas/{apartada['id']}/documentos/{doc['id']}/archivo", headers=client_h)
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(res.content)).format == "JPEG"


@pytest.mark.parametrize(
    ("requisito", "data", "fragmento"),
    [
        ("contrato", b"esto no es ni pdf ni imagen", "PDF o una foto"),
        (
            "contrato",
            b"%PDF-1.4 " + b"0" * (get_settings().max_upload_mb * 1024 * 1024),
            "supera el máximo",
        ),
        ("licencia_federal", PDF, "no pide un documento"),  # no es un requisito de esta renta
        ("anticipo", PDF, "no pide un documento"),  # es una condición, no un documento
        ("inventado", PDF, "no pide un documento"),
    ],
    ids=["no-es-archivo", "mas-de-5-mb", "requisito-ajeno", "condicion", "inexistente"],
)
def test_documentos_invalidos(client, client_h, apartada, requisito, data, fragmento) -> None:
    res = subir(client, client_h, apartada["id"], requisito, data)
    assert res.status_code == 422 and fragmento in res.json()["detail"]
    assert cumplimiento_de(client, client_h, apartada["id"])["documentos"] == []


def test_solo_se_sube_mientras_esta_apartada(client, client_h, staff, make_equipo) -> None:
    solicitada = pedir(client, client_h, make_equipo()["id"]).json()
    assert subir(client, client_h, solicitada["id"]).status_code == 409
    cotizar(client, staff["ventas"], solicitada["id"])
    assert subir(client, client_h, solicitada["id"]).status_code == 409


def test_un_apartado_vencido_no_admite_documentos(client, client_h, db, apartada) -> None:
    vencer(db, apartada["id"])
    assert subir(client, client_h, apartada["id"]).status_code == 409


def test_permisos_de_subida(client, client_h, otra_empresa_h, staff, apartada) -> None:
    rid = apartada["id"]
    assert subir(client, staff["ventas"], rid).status_code == 403  # el personal revisa, no sube
    assert subir(client, otra_empresa_h, rid).status_code == 404
    assert client.post(f"/rentas/{rid}/documentos", data={"requisito": "contrato"}).status_code in (
        401,
        422,
    )


def test_maximo_de_archivos_por_requisito(client, client_h, apartada) -> None:
    for _ in range(10):
        assert subir(client, client_h, apartada["id"]).status_code == 201
    assert subir(client, client_h, apartada["id"]).status_code == 409
    assert (
        subir(client, client_h, apartada["id"], "poliza").status_code == 201
    )  # otro requisito, otro cupo


def test_descargar_documentos(client, client_h, otra_empresa_h, staff, apartada) -> None:
    rid = apartada["id"]
    doc = subir(client, client_h, rid).json()
    url = f"/rentas/{rid}/documentos/{doc['id']}/archivo"
    for headers in (client_h, staff["ventas"], staff["admin"]):
        res = client.get(url, headers=headers)
        assert res.status_code == 200 and res.content == PDF
        assert (
            res.headers["content-type"] == "application/pdf"
            and res.headers["cache-control"] == "no-store"
        )
    assert client.get(url, headers=otra_empresa_h).status_code == 404
    assert client.get(url).status_code == 401
    assert (
        client.get(f"/rentas/{rid}/documentos/{uuid.uuid4()}/archivo", headers=client_h).status_code
        == 404
    )


def test_aprobar_un_documento(client, client_h, staff, apartada) -> None:
    rid = apartada["id"]
    doc = subir(client, client_h, rid).json()
    res = revisar_doc(client, staff["ventas"], rid, doc["id"])
    assert res.status_code == 200
    assert situaciones(res.json())["contrato"] == "cumplido"
    assert (
        res.json()["documentos"][0]["estado"] == "aprobado"
        and res.json()["documentos"][0]["revisado_at"]
    )


def test_rechazar_un_documento_exige_motivo_y_avisa_al_cliente(
    client, client_h, staff, apartada, outbox
) -> None:
    rid = apartada["id"]
    doc = subir(client, client_h, rid, "poliza").json()
    assert revisar_doc(client, staff["ventas"], rid, doc["id"], aprobado=False).status_code == 422
    assert (
        revisar_doc(client, staff["ventas"], rid, doc["id"], aprobado=False, nota="no").status_code
        == 422
    )
    outbox.clear()
    res = revisar_doc(
        client, staff["ventas"], rid, doc["id"], aprobado=False, nota="La póliza está vencida"
    )
    assert situaciones(res.json())["poliza"] == "rechazado"
    assert "La póliza está vencida" in outbox.to("titular@constructora-prueba.com")[0].body
    # Sube una versión nueva y vuelve a revisión.
    subir(client, client_h, rid, "poliza")
    assert situaciones(cumplimiento_de(client, client_h, rid))["poliza"] == "en_revision"


def test_un_documento_no_se_revisa_dos_veces_ni_lo_revisa_el_cliente(
    client, client_h, staff, apartada
) -> None:
    rid = apartada["id"]
    doc = subir(client, client_h, rid).json()
    assert revisar_doc(client, client_h, rid, doc["id"]).status_code == 403
    assert revisar_doc(client, staff["ventas"], rid, doc["id"]).status_code == 200
    assert (
        revisar_doc(
            client, staff["admin"], rid, doc["id"], aprobado=False, nota="Cambié de idea"
        ).status_code
        == 409
    )
    assert revisar_doc(client, staff["ventas"], rid, uuid.uuid4()).status_code == 404


# ---------------------------------------------------------------- pagos


def test_el_cliente_reporta_una_transferencia(client, client_h, apartada) -> None:
    res = pagar(client, client_h, apartada["id"])
    assert res.status_code == 201, res.text
    pago = res.json()
    assert (
        pago["monto"] == ANTICIPO
        and pago["estado"] == "pendiente"
        and pago["referencia"] == "SPEI123"
    )
    assert pago["reportado_por_nombre"] == "Titular Prueba"
    c = cumplimiento_de(client, client_h, apartada["id"])
    assert situaciones(c)["anticipo"] == "en_revision"
    assert c["pagado"] == 0  # todavía no está confirmado


def test_un_pago_parcial_no_cubre_el_anticipo(client, client_h, staff, apartada) -> None:
    rid = apartada["id"]
    pago = pagar(client, client_h, rid, monto=5000).json()
    assert situaciones(cumplimiento_de(client, client_h, rid))["anticipo"] == "pendiente"
    res = revisar_pago(client, staff["ventas"], rid, pago["id"])
    assert res.json()["pagado"] == 5000 and situaciones(res.json())["anticipo"] == "pendiente"
    segundo = pagar(client, client_h, rid, monto=6031.6).json()
    res = revisar_pago(client, staff["ventas"], rid, segundo["id"])
    assert res.json()["pagado"] == ANTICIPO and situaciones(res.json())["anticipo"] == "cumplido"


@pytest.mark.parametrize(
    ("campos", "codigo", "fragmento"),
    [
        ({"monto": 0}, 422, ""),
        ({"monto": -5}, 422, ""),
        ({"monto": 100.123}, 422, ""),
        ({"monto": 999999}, 409, "mayor que el saldo"),
        ({"fecha": (datetime.now(UTC) + timedelta(days=3)).date().isoformat()}, 422, "futura"),
        ({"fecha": "no-es-fecha"}, 422, ""),
        ({"data": b"esto no es un comprobante"}, 422, "PDF o una foto"),
    ],
)
def test_pagos_invalidos(client, client_h, apartada, campos, codigo, fragmento) -> None:
    res = pagar(client, client_h, apartada["id"], **campos)
    assert res.status_code == codigo, res.text
    assert fragmento in res.text
    assert cumplimiento_de(client, client_h, apartada["id"])["pagos"] == []


def test_pagos_solo_con_cotizacion_aceptada_y_por_el_cliente(
    client, client_h, staff, otra_empresa_h, make_equipo, apartada
) -> None:
    solicitada = pedir(client, client_h, make_equipo()["id"]).json()
    assert pagar(client, client_h, solicitada["id"]).status_code == 409
    assert pagar(client, staff["ventas"], apartada["id"]).status_code == 403
    assert pagar(client, otra_empresa_h, apartada["id"]).status_code == 404


def test_descargar_el_comprobante(client, client_h, otra_empresa_h, staff, apartada) -> None:
    rid = apartada["id"]
    pago = pagar(client, client_h, rid, data=png()).json()
    url = f"/rentas/{rid}/pagos/{pago['id']}/comprobante"
    assert client.get(url, headers=staff["ventas"]).headers["content-type"] == "image/jpeg"
    assert client.get(url, headers=client_h).status_code == 200
    assert client.get(url, headers=otra_empresa_h).status_code == 404


def test_confirmar_y_rechazar_pagos(client, client_h, staff, apartada, outbox) -> None:
    rid = apartada["id"]
    malo = pagar(client, client_h, rid, monto=1000, referencia="MAL").json()
    bueno = pagar(client, client_h, rid, monto=2000, referencia="BIEN").json()
    assert (
        revisar_pago(client, staff["ventas"], rid, malo["id"], aprobado=False).status_code == 422
    )  # sin motivo
    outbox.clear()
    res = revisar_pago(
        client, staff["ventas"], rid, malo["id"], aprobado=False, nota="No aparece en el banco"
    )
    assert res.json()["pagado"] == 0
    assert "No aparece en el banco" in outbox.to("titular@constructora-prueba.com")[0].body
    res = revisar_pago(client, staff["admin"], rid, bueno["id"])
    assert res.json()["pagado"] == 2000 and res.json()["saldo"] == TOTAL - 2000
    estados = {p["referencia"]: p["estado"] for p in res.json()["pagos"]}
    assert estados == {"MAL": "rechazado", "BIEN": "aprobado"}
    assert revisar_pago(client, staff["ventas"], rid, bueno["id"]).status_code == 409  # ya revisado
    assert revisar_pago(client, client_h, rid, bueno["id"]).status_code == 403


def test_no_se_confirma_mas_de_lo_que_vale_la_renta(client, client_h, staff, apartada) -> None:
    rid = apartada["id"]
    primero = pagar(client, client_h, rid, monto=30000).json()
    revisar_pago(client, staff["ventas"], rid, primero["id"])
    segundo = pagar(client, client_h, rid, monto=6772).json()  # justo lo que falta: cabe
    assert revisar_pago(client, staff["ventas"], rid, segundo["id"]).json()["saldo"] == 0
    assert pagar(client, client_h, rid, monto=1).status_code == 409  # ya está pagada


def test_dos_pagos_pendientes_que_juntos_pasan_del_total(client, client_h, staff, apartada) -> None:
    rid = apartada["id"]
    a = pagar(client, client_h, rid, monto=30000).json()
    b = pagar(client, client_h, rid, monto=30000).json()  # cada uno cabe solo; juntos no
    assert revisar_pago(client, staff["ventas"], rid, a["id"]).status_code == 200
    res = revisar_pago(client, staff["ventas"], rid, b["id"])
    assert res.status_code == 409 and "rebasaría" in res.json()["detail"]


# ---------------------------------------------------------------- confirmación automática


def test_al_cumplir_todo_la_renta_se_confirma_sola(
    client, client_h, staff, apartada, db, outbox
) -> None:
    rid = apartada["id"]
    outbox.clear()
    res = completar(client, client_h, staff, rid)
    assert res.json()["confirmada"] is True
    assert all(i["situacion"] == "cumplido" for i in res.json()["checklist"])

    renta = client.get(f"/rentas/{rid}", headers=client_h).json()
    assert renta["estado"] == "confirmada" and renta["vence_en"] is None
    bloqueo = db.query(Bloqueo).filter_by(estado=BloqueoEstado.ACTIVO).one()
    assert bloqueo.tipo == BloqueoTipo.RENTA and bloqueo.vence_en is None  # ya no vence
    correo = [m for m in outbox.to("titular@constructora-prueba.com") if "confirmada" in m.subject]
    assert len(correo) == 1


@pytest.mark.parametrize(
    "orden",
    [
        ("anticipo", "contrato", "poliza"),
        ("poliza", "anticipo", "contrato"),
        ("contrato", "poliza", "anticipo"),
    ],
)
def test_el_orden_en_que_se_cumple_no_importa(client, client_h, staff, apartada, orden) -> None:
    rid = apartada["id"]
    for paso in orden:
        assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "apartada"
        if paso == "anticipo":
            revisar_pago(client, staff["ventas"], rid, pagar(client, client_h, rid).json()["id"])
        else:
            revisar_doc(
                client, staff["ventas"], rid, subir(client, client_h, rid, paso).json()["id"]
            )
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "confirmada"


def test_nada_se_confirma_con_requisitos_a_medias(client, client_h, staff, apartada) -> None:
    rid = apartada["id"]
    revisar_doc(client, staff["ventas"], rid, subir(client, client_h, rid, "contrato").json()["id"])
    revisar_pago(client, staff["ventas"], rid, pagar(client, client_h, rid).json()["id"])
    # Falta la póliza: un documento subido pero sin aprobar tampoco cuenta.
    subir(client, client_h, rid, "poliza")
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "apartada"
    assert cumplimiento_de(client, client_h, rid)["confirmada"] is False


def test_una_renta_confirmada_sigue_bloqueando_el_equipo(
    client, client_h, otra_empresa_h, staff, apartada
) -> None:
    completar(client, client_h, staff, apartada["id"])
    assert pedir(client, otra_empresa_h, apartada["equipo_id"]).status_code == 409
    # Y ya no admite más documentos, pero sí abonos.
    assert subir(client, client_h, apartada["id"]).status_code == 409
    assert pagar(client, client_h, apartada["id"], monto=1000).status_code == 201


def test_condiciones_verificadas_a_mano(
    client, client_h, staff, make_equipo, categoria, admin_h
) -> None:
    """Un equipo que viaja en lowboy que el cliente recoge exige verificar que traiga el suyo."""
    equipo = make_equipo(requiere_lowboy=True)
    renta = apartar(client, client_h, staff["ventas"], equipo["id"], transporte="recoge")
    rid = renta["id"]
    c = cumplimiento_de(client, client_h, rid)
    assert situaciones(c)["lowboy_propio"] == "pendiente"

    # Entrega todo lo demás: sin la condición no se confirma.
    completar(client, client_h, staff, rid)
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "apartada"

    res = client.post(
        f"/rentas/{rid}/condiciones/lowboy_propio", json={"cumplida": True}, headers=staff["ventas"]
    )
    assert res.status_code == 200 and res.json()["confirmada"] is True
    assert client.get(f"/rentas/{rid}", headers=client_h).json()["estado"] == "confirmada"


def test_una_condicion_se_puede_desmarcar(client, client_h, staff, make_equipo) -> None:
    renta = apartar(
        client,
        client_h,
        staff["ventas"],
        make_equipo(requiere_lowboy=True)["id"],
        transporte="recoge",
    )
    url = f"/rentas/{renta['id']}/condiciones/lowboy_propio"
    client.post(url, json={"cumplida": True}, headers=staff["ventas"])
    res = client.post(url, json={"cumplida": False}, headers=staff["ventas"])
    assert situaciones(res.json())["lowboy_propio"] == "pendiente"


@pytest.mark.parametrize("codigo", ["anticipo", "contrato", "inventada"])
def test_solo_se_marcan_a_mano_las_condiciones_que_no_son_pago_ni_documento(
    client, client_h, staff, apartada, codigo
) -> None:
    res = client.post(
        f"/rentas/{apartada['id']}/condiciones/{codigo}",
        json={"cumplida": True},
        headers=staff["ventas"],
    )
    assert res.status_code == 422


def test_las_condiciones_son_del_personal(client, client_h, staff, make_equipo) -> None:
    renta = apartar(
        client,
        client_h,
        staff["ventas"],
        make_equipo(requiere_lowboy=True)["id"],
        transporte="recoge",
    )
    url = f"/rentas/{renta['id']}/condiciones/lowboy_propio"
    assert client.post(url, json={"cumplida": True}, headers=client_h).status_code == 403
    assert client.post(url, json={"cumplida": True}).status_code == 401


# ---------------------------------------------------------------- concurrencia


def test_dos_revisiones_simultaneas_de_lo_ultimo_confirman_la_renta(
    client, client_h, staff, apartada, db
) -> None:
    """Dos personas aprueban a la vez los dos últimos requisitos: la renta debe quedar confirmada
    (sin el bloqueo de la renta, cada una vería a la otra como pendiente y no la confirmaría)."""
    rid = apartada["id"]
    docs = {r: subir(client, client_h, rid, r).json()["id"] for r in ("contrato", "poliza")}
    revisar_pago(client, staff["ventas"], rid, pagar(client, client_h, rid).json()["id"])

    barrier = threading.Barrier(2)
    resultados: list[bool] = []

    def aprobar(doc_id: str) -> None:
        with SessionLocal() as session:
            renta = session.get(Renta, uuid.UUID(rid))
            persona = accounts.get_by_email(session, "ventas@chrisco-pruebas.com")
            barrier.wait()
            _, confirmada = cumplimiento.review_document(
                session, renta, uuid.UUID(doc_id), persona, RevisionIn(aprobado=True)
            )
            resultados.append(confirmada)

    hilos = [threading.Thread(target=aprobar, args=(d,)) for d in docs.values()]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(resultados) == [False, True]  # exactamente una la confirma
    db.expire_all()
    assert db.get(Renta, uuid.UUID(rid)).estado == RentaEstado.CONFIRMADA


def test_confirmar_dos_veces_no_es_posible(client, client_h, staff, apartada, db) -> None:
    completar(client, client_h, staff, apartada["id"])
    renta = db.get(Renta, uuid.UUID(apartada["id"]))
    with SessionLocal() as session:
        again = session.get(Renta, renta.id)
        assert cumplimiento.try_confirm(session, again) is False  # ya no está apartada
    with pytest.raises(Conflict):
        cumplimiento._require_open(renta)


# ---------------------------------------------------------------- base de datos


def test_la_base_de_datos_exige_montos_positivos(client, client_h, apartada, db) -> None:
    from sqlalchemy.exc import IntegrityError

    pagar(client, client_h, apartada["id"])
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE pagos SET monto = 0"))
    db.rollback()


def test_el_equipo_de_otra_renta_no_se_mezcla(
    client, client_h, staff, make_equipo, categoria
) -> None:
    a = apartar(client, client_h, staff["ventas"], make_equipo()["id"], transporte="recoge")
    b = apartar(client, client_h, staff["ventas"], make_equipo()["id"], transporte="recoge")
    revisar_doc(
        client, staff["ventas"], a["id"], subir(client, client_h, a["id"], "contrato").json()["id"]
    )
    assert situaciones(cumplimiento_de(client, client_h, b["id"]))["contrato"] == "pendiente"
    assert auth  # (helper importado para otros casos)
    assert equipo_payload

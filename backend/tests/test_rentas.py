import re
import threading
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import cli
from app.core.config import get_settings
from app.core.errors import Conflict
from app.db.session import SessionLocal
from app.models.empresa import Empresa
from app.models.renta import Renta, RentaEstado
from app.models.user import Role
from app.schemas.renta import SolicitudIn
from app.services import accounts, rentas
from tests.conftest import auth, equipo_payload
from tests.rentas_helpers import h, pedir, solicitud, vencer

# ---------------------------------------------------------------- vista previa


def test_la_vista_previa_dice_si_esta_libre_y_que_se_pedira(client, client_h, make_equipo) -> None:
    equipo = make_equipo(requiere_lowboy=True)
    res = client.post("/rentas/solicitudes/preview", json=solicitud(equipo["id"]), headers=client_h)
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["disponible"] is True
    assert [r["codigo"] for r in cuerpo["requisitos"]][:3] == ["contrato", "poliza", "anticipo"]
    assert "flete_lowboy" in [r["codigo"] for r in cuerpo["requisitos"]]


def test_la_vista_previa_no_reserva_nada(client, client_h, otra_empresa_h, make_equipo) -> None:
    equipo = make_equipo()
    client.post("/rentas/solicitudes/preview", json=solicitud(equipo["id"]), headers=client_h)
    assert pedir(client, otra_empresa_h, equipo["id"]).status_code == 201  # sigue libre


def test_la_vista_previa_avisa_si_esta_ocupado(
    client, client_h, otra_empresa_h, make_equipo
) -> None:
    equipo = make_equipo()
    pedir(client, otra_empresa_h, equipo["id"])
    res = client.post(
        "/rentas/solicitudes/preview", json=solicitud(equipo["id"], 26, 30), headers=client_h
    )
    assert res.json()["disponible"] is False


def test_solo_un_cliente_aprobado_puede_solicitar(
    client, admin_h, client_h, make_equipo, register, verify_email, login
) -> None:
    equipo = make_equipo()
    body = solicitud(equipo["id"])
    assert client.post("/rentas/solicitudes", json=body).status_code == 401
    assert (
        client.post("/rentas/solicitudes", json=body, headers=admin_h).status_code == 403
    )  # personal
    assert client.post("/rentas/solicitudes/preview", json=body, headers=admin_h).status_code == 403
    register(rfc="OTR020202XY9", email="otro@otra-empresa.com")
    verify_email("otro@otra-empresa.com")
    pendiente = auth(login("otro@otra-empresa.com"))
    assert client.post("/rentas/solicitudes", json=body, headers=pendiente).status_code == 403


def test_un_equipo_fuera_de_catalogo_no_se_solicita(
    client, client_h, admin_h, categoria, make_equipo
) -> None:
    equipo = make_equipo()
    client.put(
        f"/admin/equipos/{equipo['id']}",
        json=equipo_payload(categoria["id"], 1, status="mantenimiento"),
        headers=admin_h,
    )
    assert pedir(client, client_h, equipo["id"]).status_code == 404
    assert pedir(client, client_h, str(uuid.uuid4())).status_code == 404


# ---------------------------------------------------------------- crear la solicitud


def test_la_solicitud_reserva_el_equipo_y_arma_el_mensaje(
    client, client_h, make_equipo, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "sales_whatsapp_number", "5217221234567")
    equipo = make_equipo(requiere_lowboy=True)
    res = pedir(client, client_h, equipo["id"], notas="Entrar por el portón sur")
    assert res.status_code == 201, res.text
    r = res.json()

    assert re.fullmatch(r"CHR-\d{4}-\d{5}", r["folio"])
    assert r["estado"] == "solicitada" and r["equipo_codigo"] == "EQ-001"
    assert r["empresa_razon_social"] == "Constructora Prueba SA de CV"
    assert r["solicitante_nombre"] == "Titular Prueba" and r["notas"] == "Entrar por el portón sur"
    assert "flete_lowboy" in [x["codigo"] for x in r["requisitos"]]
    minutos = (datetime.fromisoformat(r["vence_en"]) - datetime.now(UTC)).total_seconds() / 60
    assert 19 < minutos <= 20  # reservado 20 minutos

    mensaje = r["whatsapp"]["mensaje"]
    assert (
        r["folio"] in mensaje
        and "Pavimentadora 1 (EQ-001)" in mensaje
        and "Entrar por el portón sur" in mensaje
    )
    assert r["whatsapp"]["url"].startswith("https://wa.me/5217221234567?text=")


def test_sin_numero_de_ventas_configurado_igual_se_entrega_el_mensaje(
    client, client_h, make_equipo
) -> None:
    equipo = make_equipo()
    r = pedir(client, client_h, equipo["id"]).json()
    assert r["whatsapp"]["url"] is None and r["folio"] in r["whatsapp"]["mensaje"]


def test_mientras_esta_reservado_nadie_mas_puede_pedirlo(
    client, client_h, otra_empresa_h, make_equipo
) -> None:
    equipo = make_equipo()
    assert pedir(client, client_h, equipo["id"], 24, 32).status_code == 201
    choque = pedir(client, otra_empresa_h, equipo["id"], 30, 40)
    assert choque.status_code == 409 and "no está disponible" in choque.json()["detail"]
    assert pedir(client, otra_empresa_h, equipo["id"], 32, 40).status_code == 201  # justo después


def test_la_reserva_se_ve_en_la_disponibilidad_del_catalogo(client, client_h, make_equipo) -> None:
    equipo = make_equipo()
    pedir(client, client_h, equipo["id"], 24, 32)
    params = {"desde": h(26).isoformat(), "hasta": h(28).isoformat()}
    assert (
        client.get(
            f"/equipos/{equipo['id']}/disponibilidad", params=params, headers=client_h
        ).json()["disponible"]
        is False
    )


@pytest.mark.parametrize(
    ("cambio", "fragmento"),
    [
        ({"desde": h(-2).isoformat(), "hasta": h(5).isoformat()}, "futuro"),
        ({"desde": h(24).isoformat(), "hasta": h(24.5).isoformat()}, "mínima"),
        ({"desde": h(30).isoformat(), "hasta": h(24).isoformat()}, "posterior"),
        ({"desde": "2030-01-01T10:00:00", "hasta": "2030-01-02T10:00:00"}, "timezone"),
        ({"destino": "x"}, ""),
        ({"destino": ""}, ""),
        ({"notas": "n" * 501}, ""),
        ({"operador_modo": "nadie"}, ""),
        ({"transporte": "volando"}, ""),
        ({"equipo_id": "no-es-uuid"}, ""),
    ],
)
def test_validaciones_de_la_solicitud(client, client_h, make_equipo, cambio, fragmento) -> None:
    equipo = make_equipo()
    body = {**solicitud(equipo["id"]), **cambio}
    res = client.post("/rentas/solicitudes", json=body, headers=client_h)
    assert res.status_code == 422, res.text
    assert fragmento in res.text


def test_los_folios_no_se_repiten(client, client_h, make_equipo) -> None:
    folios = {pedir(client, client_h, make_equipo()["id"]).json()["folio"] for _ in range(3)}
    assert len(folios) == 3


def test_los_requisitos_quedan_como_se_mostraron(
    client, client_h, admin_h, categoria, make_equipo
) -> None:
    equipo = make_equipo(requiere_lowboy=True)
    renta = pedir(client, client_h, equipo["id"]).json()
    # El equipo cambia después (ya no necesita lowboy): la solicitud conserva lo que se le mostró.
    client.put(
        f"/admin/equipos/{equipo['id']}",
        json=equipo_payload(categoria["id"], 1, requiere_lowboy=False),
        headers=admin_h,
    )
    guardada = client.get(f"/rentas/{renta['id']}", headers=client_h).json()
    assert [r["codigo"] for r in guardada["requisitos"]] == [
        r["codigo"] for r in renta["requisitos"]
    ]
    assert "flete_lowboy" in [r["codigo"] for r in guardada["requisitos"]]


# ---------------------------------------------------------------- límite de solicitudes abiertas


def test_una_empresa_no_puede_acaparar_equipos(client, client_h, make_equipo) -> None:
    ids = [make_equipo()["id"] for _ in range(4)]
    for equipo_id in ids[:3]:
        assert pedir(client, client_h, equipo_id).status_code == 201
    res = pedir(client, client_h, ids[3])
    assert res.status_code == 409 and "3 solicitudes abiertas" in res.json()["detail"]


def test_cancelar_o_vencer_libera_un_lugar(client, client_h, db, make_equipo) -> None:
    ids = [make_equipo()["id"] for _ in range(5)]
    creadas = [pedir(client, client_h, i).json() for i in ids[:3]]
    assert pedir(client, client_h, ids[3]).status_code == 409
    client.post(f"/rentas/{creadas[0]['id']}/cancelar", headers=client_h)
    assert pedir(client, client_h, ids[3]).status_code == 201
    vencer(db, creadas[1]["id"])
    assert pedir(client, client_h, ids[4]).status_code == 201


def test_el_limite_es_por_empresa_no_global(client, client_h, otra_empresa_h, make_equipo) -> None:
    for _ in range(3):
        pedir(client, client_h, make_equipo()["id"])
    assert pedir(client, otra_empresa_h, make_equipo()["id"]).status_code == 201


def test_dos_solicitudes_simultaneas_no_pasan_del_limite(db, client_h, make_equipo, client) -> None:
    """Dos pestañas o un doble clic: con 2 abiertas y límite 3, solo una más puede entrar."""
    for _ in range(2):
        pedir(client, client_h, make_equipo()["id"])
    nuevos = [make_equipo()["id"] for _ in range(2)]
    empresa_id = db.query(Empresa).one().id
    barrier = threading.Barrier(2)
    resultados: list[str] = []

    def solicitar(equipo_id: str) -> None:
        with SessionLocal() as session:
            user = accounts.get_by_email(session, "titular@constructora-prueba.com")
            empresa = session.get(Empresa, empresa_id)
            datos = SolicitudIn.model_validate(solicitud(equipo_id))
            barrier.wait()
            try:
                rentas.create_request(session, user, empresa, datos)
                resultados.append("ok")
            except Conflict:
                resultados.append("conflicto")

    hilos = [threading.Thread(target=solicitar, args=(e,)) for e in nuevos]
    for t in hilos:
        t.start()
    for t in hilos:
        t.join()
    assert sorted(resultados) == ["conflicto", "ok"]
    assert db.query(Renta).filter_by(estado=RentaEstado.SOLICITADA).count() == 3


# ---------------------------------------------------------------- consultar


def test_cada_empresa_ve_solo_sus_solicitudes(
    client, client_h, otra_empresa_h, admin_h, ventas_h, make_equipo
) -> None:
    mia = pedir(client, client_h, make_equipo()["id"]).json()
    ajena = pedir(client, otra_empresa_h, make_equipo()["id"]).json()

    assert [r["id"] for r in client.get("/rentas", headers=client_h).json()["items"]] == [mia["id"]]
    assert [r["id"] for r in client.get("/rentas", headers=otra_empresa_h).json()["items"]] == [
        ajena["id"]
    ]
    for personal in (admin_h, ventas_h):
        assert client.get("/rentas", headers=personal).json()["total"] == 2
        assert client.get(f"/rentas/{mia['id']}", headers=personal).status_code == 200

    assert (
        client.get(f"/rentas/{ajena['id']}", headers=client_h).status_code == 404
    )  # ni siquiera «existe»
    assert client.get(f"/rentas/{ajena['id']}/whatsapp", headers=client_h).status_code == 404
    assert client.post(f"/rentas/{ajena['id']}/cancelar", headers=client_h).status_code == 404
    assert client.get(f"/rentas/{uuid.uuid4()}", headers=client_h).status_code == 404


def test_listar_exige_sesion_y_acceso(client, make_user, login, client_h) -> None:
    assert client.get("/rentas").status_code == 401
    make_user("operador@chrisco-pruebas.com", Role.OPERADOR)
    assert (
        client.get("/rentas", headers=auth(login("operador@chrisco-pruebas.com"))).status_code
        == 403
    )


def test_filtros_y_paginacion(client, client_h, admin_h, make_equipo) -> None:
    a, b, c = (make_equipo() for _ in range(3))
    ra = pedir(client, client_h, a["id"]).json()
    pedir(client, client_h, b["id"])
    pedir(client, client_h, c["id"])
    client.post(f"/rentas/{ra['id']}/cancelar", headers=client_h)

    assert client.get("/rentas?estado=cancelada", headers=admin_h).json()["total"] == 1
    assert client.get("/rentas?estado=solicitada", headers=admin_h).json()["total"] == 2
    assert client.get(f"/rentas?q={ra['folio']}", headers=admin_h).json()["total"] == 1
    assert client.get("/rentas?q=constructora prueba", headers=admin_h).json()["total"] == 3
    assert client.get("/rentas?q=Pavimentadora 2", headers=admin_h).json()["total"] == 1
    assert client.get("/rentas?q=nada-asi", headers=admin_h).json()["total"] == 0
    pagina = client.get("/rentas?limit=2&offset=0", headers=admin_h).json()
    assert pagina["total"] == 3 and len(pagina["items"]) == 2
    assert (
        pagina["items"][0]["created_at"] >= pagina["items"][1]["created_at"]
    )  # las nuevas primero
    assert client.get("/rentas?limit=0", headers=admin_h).status_code == 422


def test_el_mensaje_se_puede_pedir_de_nuevo(client, client_h, make_equipo) -> None:
    creada = pedir(client, client_h, make_equipo()["id"]).json()
    otra_vez = client.get(f"/rentas/{creada['id']}/whatsapp", headers=client_h).json()
    assert otra_vez["mensaje"] == creada["whatsapp"]["mensaje"]


# ---------------------------------------------------------------- cancelar y vencer


def test_cancelar_libera_el_equipo_al_instante(
    client, client_h, otra_empresa_h, make_equipo
) -> None:
    equipo = make_equipo()
    renta = pedir(client, client_h, equipo["id"]).json()
    assert pedir(client, otra_empresa_h, equipo["id"]).status_code == 409

    res = client.post(f"/rentas/{renta['id']}/cancelar", headers=client_h)
    assert (
        res.status_code == 200
        and res.json()["estado"] == "cancelada"
        and res.json()["vence_en"] is None
    )
    assert pedir(client, otra_empresa_h, equipo["id"]).status_code == 201
    assert (
        client.post(f"/rentas/{renta['id']}/cancelar", headers=client_h).status_code == 409
    )  # ya no


def test_el_personal_tambien_puede_cancelar(client, client_h, ventas_h, make_equipo) -> None:
    renta = pedir(client, client_h, make_equipo()["id"]).json()
    assert (
        client.post(f"/rentas/{renta['id']}/cancelar", headers=ventas_h).json()["estado"]
        == "cancelada"
    )


def test_una_solicitud_sin_respuesta_vence_a_los_20_minutos(
    client, client_h, otra_empresa_h, db, make_equipo
) -> None:
    equipo = make_equipo()
    renta = pedir(client, client_h, equipo["id"]).json()
    vencer(db, renta["id"])

    vista = client.get(f"/rentas/{renta['id']}", headers=client_h).json()
    assert vista["estado"] == "vencida" and vista["vence_en"] is None
    assert client.get("/rentas?estado=vencida", headers=client_h).json()["total"] == 1
    assert (
        pedir(client, otra_empresa_h, equipo["id"]).status_code == 201
    )  # el equipo volvió a estar libre
    assert client.post(f"/rentas/{renta['id']}/cancelar", headers=client_h).status_code == 409


def test_vencer_no_toca_las_solicitudes_vigentes(client, client_h, db, make_equipo) -> None:
    vieja = pedir(client, client_h, make_equipo()["id"]).json()
    vigente = pedir(client, client_h, make_equipo()["id"]).json()
    vencer(db, vieja["id"])
    estados = {
        r["id"]: r["estado"] for r in client.get("/rentas", headers=client_h).json()["items"]
    }
    assert estados == {vieja["id"]: "vencida", vigente["id"]: "solicitada"}


def test_el_comando_expire_holds_vence_las_solicitudes(
    client, client_h, db, make_equipo, capsys, monkeypatch
) -> None:
    renta = pedir(client, client_h, make_equipo()["id"]).json()
    vencer(db, renta["id"])
    monkeypatch.setattr("sys.argv", ["app.cli", "expire-holds"])
    cli.main()
    assert "1 reserva(s) vencida(s)" in capsys.readouterr().out
    db.expire_all()
    assert db.get(Renta, uuid.UUID(renta["id"])).estado == RentaEstado.VENCIDA


# ---------------------------------------------------------------- base de datos


def test_la_base_de_datos_protege_la_renta(client, client_h, db, make_equipo) -> None:
    renta = pedir(client, client_h, make_equipo()["id"]).json()
    otra = pedir(client, client_h, make_equipo()["id"]).json()
    with pytest.raises(IntegrityError):  # hasta debe ser posterior a desde
        db.execute(text("UPDATE rentas SET hasta = desde WHERE id = :id"), {"id": renta["id"]})
    db.rollback()
    with pytest.raises(IntegrityError):  # un folio no se repite
        db.execute(
            text("UPDATE rentas SET folio = :folio WHERE id = :id"),
            {"folio": renta["folio"], "id": otra["id"]},
        )
    db.rollback()

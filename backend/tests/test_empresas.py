import pytest
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models.empresa import Empresa, EmpresaStatus
from app.models.user import Role, User
from app.services import accounts
from tests.conftest import COMPANY, PASSWORD, PDF, auth, token_from, uploads_count

OTHER = {"rfc": "OTR020202XY9", "email": "otro@otra-empresa.com", "razon_social": "Otra SA"}


# ---------------------------------------------------------------- registro público


def test_registro_crea_empresa_pendiente_y_titular_sin_verificar(register, db, outbox) -> None:
    res = register()
    assert res.status_code == 201

    empresa = db.query(Empresa).one()
    assert empresa.status == EmpresaStatus.PENDIENTE
    assert empresa.rfc == "CPR010101AB1"
    owner = empresa.owner
    assert owner and owner.role == Role.CLIENTE and owner.email_verified_at is None
    assert uploads_count() == 1
    assert len(outbox.to(COMPANY["email"])) == 1


def test_registro_normaliza_rfc_y_sitio_web(register, db) -> None:
    register(rfc=" cpr-010101 ab1 ", sitio_web="Constructora-Prueba.com")
    empresa = db.query(Empresa).one()
    assert empresa.rfc == "CPR010101AB1"
    assert empresa.sitio_web.startswith("https://constructora-prueba.com")


def test_registro_acepta_rfc_de_persona_fisica(register, db) -> None:
    assert register(rfc="PEGJ800101AB1").status_code == 201


@pytest.mark.parametrize(
    "rfc",
    ["", "ABC", "CPR010101", "CPR011301AB1", "CPR010132AB1", "XAXX010101000", "XEXX010101000"],
)
def test_registro_rechaza_rfc_invalido(register, rfc) -> None:
    assert register(rfc=rfc).status_code == 422


def test_registro_rechaza_archivo_que_no_es_pdf(register) -> None:
    res = register(constancia=b"GIF89a esto no es un pdf")
    assert res.status_code == 422
    assert uploads_count() == 0


def test_registro_rechaza_archivo_demasiado_grande(register) -> None:
    big = PDF + b"0" * (get_settings().max_upload_mb * 1024 * 1024)
    assert register(constancia=big).status_code == 422
    assert uploads_count() == 0


def test_registro_rechaza_contrasena_corta_y_correo_invalido(register) -> None:
    assert register(password="corta").status_code == 422
    assert register(email="no-es-correo").status_code == 422


def test_registro_rechaza_rfc_duplicado_sin_dejar_archivos(register) -> None:
    assert register().status_code == 201
    res = register(email="otro@otra-empresa.com")
    assert res.status_code == 409
    assert uploads_count() == 1


def test_registro_rechaza_correo_duplicado(register) -> None:
    assert register().status_code == 201
    assert register(rfc=OTHER["rfc"]).status_code == 409
    assert uploads_count() == 1


# ---------------------------------------------------------------- verificación de correo


def test_no_puede_entrar_sin_verificar_el_correo(register, client) -> None:
    register()
    ok = client.post("/auth/login", json={"email": COMPANY["email"], "password": PASSWORD})
    assert ok.status_code == 403
    # Con contraseña incorrecta sigue siendo 401: no se revela qué correos existen.
    bad = client.post("/auth/login", json={"email": COMPANY["email"], "password": "incorrecta1"})
    assert bad.status_code == 401


def test_verificar_correo_permite_entrar(register, client, outbox, login) -> None:
    register()
    token = token_from(outbox[0])
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 204
    # Repetir el enlace no falla.
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 204
    assert login(COMPANY["email"])["access_token"]


def test_verificar_con_token_invalido(client) -> None:
    assert client.post("/auth/verify-email", json={"token": "basura"}).status_code == 422


def test_reenviar_verificacion(register, client, outbox) -> None:
    register()
    outbox.clear()
    assert (
        client.post("/auth/resend-verification", json={"email": COMPANY["email"]}).status_code
        == 204
    )
    assert len(outbox.to(COMPANY["email"])) == 1
    # Un correo desconocido responde igual y no envía nada.
    outbox.clear()
    assert (
        client.post("/auth/resend-verification", json={"email": "nadie@x.com"}).status_code == 204
    )
    assert not outbox


def test_no_reenvia_verificacion_a_quien_ya_verifico(
    register, client, outbox, verify_email
) -> None:
    register()
    verify_email(COMPANY["email"])
    outbox.clear()
    client.post("/auth/resend-verification", json={"email": COMPANY["email"]})
    assert not outbox


# ---------------------------------------------------------------- área de la empresa


def test_mi_empresa_muestra_estado_y_usuarios(client, approved_owner, login) -> None:
    res = client.get("/empresa/me", headers=auth(login(**approved_owner)))
    body = res.json()
    assert res.status_code == 200
    assert body["rfc"] == COMPANY["rfc"] and body["status"] == "aprobada"
    assert body["max_users"] == 3
    assert [u["is_company_owner"] for u in body["users"]] == [True]


def test_solo_clientes_ven_mi_empresa(client, make_user, login) -> None:
    make_user()
    assert client.get("/empresa/me", headers=auth(login())).status_code == 403
    assert client.get("/empresa/me").status_code == 401


def test_solo_empresa_aprobada_puede_pasar_por_la_dependencia(
    client, register, verify_email, login, set_company_status
) -> None:
    register()
    verify_email(COMPANY["email"])
    headers = auth(login(COMPANY["email"]))
    assert client.get("/_probe/approved-client", headers=headers).status_code == 403
    set_company_status(COMPANY["rfc"], EmpresaStatus.APROBADA)
    assert client.get("/_probe/approved-client", headers=headers).status_code == 200


def test_la_base_de_datos_exige_empresa_a_los_clientes(db) -> None:
    db.add(User(email="x@x.com", full_name="X", password_hash="x", role=Role.CLIENTE))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ---------------------------------------------------------------- revisión del administrador


@pytest.fixture
def pending(register, verify_email, outbox):
    register()
    verify_email(COMPANY["email"])
    outbox.clear()


@pytest.fixture
def staff(make_user, login):
    make_user("admin@chrisco-pruebas.com", Role.ADMIN)
    make_user("ventas@chrisco-pruebas.com", Role.VENTAS)
    return {
        "admin": auth(login("admin@chrisco-pruebas.com")),
        "ventas": auth(login("ventas@chrisco-pruebas.com")),
    }


def _empresa_id(client, headers) -> str:
    return client.get("/admin/empresas", headers=headers).json()[0]["id"]


def test_el_personal_lista_empresas_con_filtro(
    client, pending, staff, register, set_company_status
) -> None:
    register(**OTHER)
    set_company_status(OTHER["rfc"], EmpresaStatus.APROBADA)
    for role in ("admin", "ventas"):
        todas = client.get("/admin/empresas", headers=staff[role]).json()
        assert len(todas) == 2
    solo = client.get("/admin/empresas?status_filter=pendiente", headers=staff["admin"]).json()
    assert [e["rfc"] for e in solo] == [COMPANY["rfc"]]
    assert solo[0]["owner_email"] == COMPANY["email"] and solo[0]["active_users"] == 1


def test_un_cliente_no_entra_al_panel_de_empresas(client, approved_owner, login) -> None:
    headers = auth(login(**approved_owner))
    assert client.get("/admin/empresas", headers=headers).status_code == 403


def test_descargar_constancia(client, pending, staff, approved_owner, login) -> None:
    empresa_id = _empresa_id(client, staff["admin"])
    for role in ("admin", "ventas"):
        res = client.get(f"/admin/empresas/{empresa_id}/constancia", headers=staff[role])
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert res.headers["cache-control"] == "no-store"
        assert res.content == PDF
    assert client.get(f"/admin/empresas/{empresa_id}/constancia").status_code == 401
    cliente = auth(login(**approved_owner))
    assert (
        client.get(f"/admin/empresas/{empresa_id}/constancia", headers=cliente).status_code == 403
    )


def test_empresa_inexistente(client, staff) -> None:
    res = client.get("/admin/empresas/00000000-0000-0000-0000-000000000000", headers=staff["admin"])
    assert res.status_code == 404


def test_aprobar_empresa(client, pending, staff, outbox, db) -> None:
    empresa_id = _empresa_id(client, staff["admin"])
    assert (
        client.post(f"/admin/empresas/{empresa_id}/aprobar", headers=staff["admin"]).status_code
        == 204
    )

    empresa = db.query(Empresa).one()
    assert empresa.status == EmpresaStatus.APROBADA
    assert empresa.reviewed_by is not None and empresa.reviewed_at is not None
    assert len(outbox.to(COMPANY["email"])) == 1
    # Ya no está pendiente: no se puede decidir dos veces.
    again = client.post(f"/admin/empresas/{empresa_id}/aprobar", headers=staff["admin"])
    assert again.status_code == 409


def test_ventas_puede_ver_pero_no_decidir(client, pending, staff) -> None:
    empresa_id = _empresa_id(client, staff["ventas"])
    assert (
        client.post(f"/admin/empresas/{empresa_id}/aprobar", headers=staff["ventas"]).status_code
        == 403
    )
    body = {"motivo": "Constancia ilegible"}
    assert (
        client.post(
            f"/admin/empresas/{empresa_id}/rechazar", json=body, headers=staff["ventas"]
        ).status_code
        == 403
    )


def test_rechazar_exige_motivo_y_lo_notifica(client, pending, staff, outbox, login) -> None:
    empresa_id = _empresa_id(client, staff["admin"])
    url = f"/admin/empresas/{empresa_id}/rechazar"
    assert client.post(url, json={"motivo": "no"}, headers=staff["admin"]).status_code == 422

    res = client.post(url, json={"motivo": "La constancia está vencida"}, headers=staff["admin"])
    assert res.status_code == 204
    assert "La constancia está vencida" in outbox.to(COMPANY["email"])[0].body

    mine = client.get("/empresa/me", headers=auth(login(COMPANY["email"]))).json()
    assert mine["status"] == "rechazada" and mine["motivo_rechazo"] == "La constancia está vencida"


def test_reenviar_tras_rechazo_vuelve_a_pendiente(client, pending, staff, login) -> None:
    empresa_id = _empresa_id(client, staff["admin"])
    client.post(
        f"/admin/empresas/{empresa_id}/rechazar",
        json={"motivo": "RFC incorrecto"},
        headers=staff["admin"],
    )
    owner = auth(login(COMPANY["email"]))

    res = client.put(
        "/empresa/me",
        data={
            "razon_social": "Constructora Corregida",
            "sitio_web": "https://corregida.mx",
            "rfc": OTHER["rfc"],
        },
        files={"constancia": ("nueva.pdf", PDF + b"\n%nueva", "application/pdf")},
        headers=owner,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "pendiente" and body["motivo_rechazo"] is None
    assert body["rfc"] == OTHER["rfc"] and body["razon_social"] == "Constructora Corregida"
    assert uploads_count() == 1  # la constancia anterior se eliminó


def test_no_se_puede_reenviar_si_no_esta_rechazada(client, pending, login) -> None:
    res = client.put(
        "/empresa/me",
        data={"razon_social": "X Y", "sitio_web": "x.com", "rfc": COMPANY["rfc"]},
        files={"constancia": ("c.pdf", PDF, "application/pdf")},
        headers=auth(login(COMPANY["email"])),
    )
    assert res.status_code == 409


def test_reenviar_con_rfc_de_otra_empresa_falla(client, pending, staff, login, register) -> None:
    register(**OTHER)
    pendientes = client.get("/admin/empresas", headers=staff["admin"]).json()
    mia = next(e for e in pendientes if e["rfc"] == COMPANY["rfc"])
    client.post(
        f"/admin/empresas/{mia['id']}/rechazar",
        json={"motivo": "Datos incorrectos"},
        headers=staff["admin"],
    )

    res = client.put(
        "/empresa/me",
        data={"razon_social": "Constructora Prueba", "sitio_web": "x.com", "rfc": OTHER["rfc"]},
        files={"constancia": ("c.pdf", PDF, "application/pdf")},
        headers=auth(login(COMPANY["email"])),
    )
    assert res.status_code == 409
    assert uploads_count() == 2  # no se dejó un archivo huérfano


# ---------------------------------------------------------------- usuarios de la empresa


def _invite(client, headers, email="uno@constructora-prueba.com", name="Compañero Uno"):
    return client.post(
        "/empresa/me/usuarios", json={"email": email, "full_name": name}, headers=headers
    )


def test_empresa_pendiente_no_puede_invitar(client, pending, login) -> None:
    assert _invite(client, auth(login(COMPANY["email"]))).status_code == 403


def test_el_maximo_es_de_tres_usuarios(client, approved_owner, login, outbox) -> None:
    owner = auth(login(**approved_owner))
    outbox.clear()
    assert _invite(client, owner, "uno@constructora-prueba.com").status_code == 201
    assert _invite(client, owner, "dos@constructora-prueba.com").status_code == 201
    tercero = _invite(client, owner, "tres@constructora-prueba.com")
    assert tercero.status_code == 409 and "3" in tercero.json()["detail"]
    assert len(outbox.to("uno@constructora-prueba.com")) == 1
    assert not outbox.to("tres@constructora-prueba.com")


def test_el_invitado_crea_su_contrasena_y_entra(client, approved_owner, login, outbox) -> None:
    owner = auth(login(**approved_owner))
    outbox.clear()
    _invite(client, owner)
    token = token_from(outbox[0])

    # Antes de aceptar no puede entrar, ni siquiera con una contraseña cualquiera.
    antes = client.post(
        "/auth/login", json={"email": "uno@constructora-prueba.com", "password": "cualquiera-123"}
    )
    assert antes.status_code == 401

    nueva = "contraseña-del-invitado-1"
    assert (
        client.post("/auth/accept-invite", json={"token": token, "password": nueva}).status_code
        == 204
    )
    tokens = login("uno@constructora-prueba.com", nueva)
    me = client.get("/auth/me", headers=auth(tokens)).json()
    assert me["role"] == "cliente"
    # El enlace es de un solo uso.
    again = client.post(
        "/auth/accept-invite", json={"token": token, "password": "otra-contraseña-99"}
    )
    assert again.status_code == 422


def test_un_invitado_no_puede_invitar_a_otros(client, approved_owner, login, outbox) -> None:
    owner = auth(login(**approved_owner))
    outbox.clear()
    _invite(client, owner)
    pwd = "contraseña-del-invitado-1"
    client.post("/auth/accept-invite", json={"token": token_from(outbox[0]), "password": pwd})
    guest = auth(login("uno@constructora-prueba.com", pwd))
    assert _invite(client, guest, "dos@constructora-prueba.com").status_code == 403
    assert client.get("/_probe/company-owner", headers=guest).status_code == 403
    assert client.get("/_probe/company-owner", headers=owner).status_code == 200


def test_invitar_un_correo_que_ya_existe(client, approved_owner, login) -> None:
    owner = auth(login(**approved_owner))
    assert _invite(client, owner, COMPANY["email"]).status_code == 409


def test_dar_de_baja_libera_el_lugar_y_cierra_sesiones(
    client, approved_owner, login, outbox, db
) -> None:
    owner = auth(login(**approved_owner))
    outbox.clear()
    _invite(client, owner, "uno@constructora-prueba.com")
    pwd = "contraseña-del-invitado-1"
    client.post("/auth/accept-invite", json={"token": token_from(outbox[0]), "password": pwd})
    guest_tokens = login("uno@constructora-prueba.com", pwd)
    _invite(client, owner, "dos@constructora-prueba.com")
    assert _invite(client, owner, "tres@constructora-prueba.com").status_code == 409

    uno = accounts.get_by_email(db, "uno@constructora-prueba.com")
    assert client.delete(f"/empresa/me/usuarios/{uno.id}", headers=owner).status_code == 204
    assert client.get("/auth/me", headers=auth(guest_tokens)).status_code == 401
    assert _invite(client, owner, "tres@constructora-prueba.com").status_code == 201


def test_se_puede_reinvitar_a_quien_fue_dado_de_baja(
    client, approved_owner, login, outbox, db
) -> None:
    owner = auth(login(**approved_owner))
    _invite(client, owner)
    uno = accounts.get_by_email(db, "uno@constructora-prueba.com")
    client.delete(f"/empresa/me/usuarios/{uno.id}", headers=owner)
    outbox.clear()
    assert _invite(client, owner, name="Compañero Uno Otra Vez").status_code == 201
    assert len(outbox.to("uno@constructora-prueba.com")) == 1


def test_no_se_puede_dar_de_baja_al_titular_ni_a_extraños(
    client, approved_owner, login, register, db
) -> None:
    owner = auth(login(**approved_owner))
    titular = accounts.get_by_email(db, COMPANY["email"])
    assert client.delete(f"/empresa/me/usuarios/{titular.id}", headers=owner).status_code == 422

    register(**OTHER)
    ajeno = accounts.get_by_email(db, OTHER["email"])
    assert client.delete(f"/empresa/me/usuarios/{ajeno.id}", headers=owner).status_code == 404

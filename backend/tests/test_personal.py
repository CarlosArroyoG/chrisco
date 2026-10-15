"""Gestión del personal desde la interfaz: altas, roles, bajas y el último administrador."""

import threading
import uuid

import pytest

from app.core.errors import Conflict
from app.db.session import SessionLocal
from app.models.user import Role, User
from app.schemas.personal import PersonalUpdate
from app.services import accounts, personal
from tests.conftest import PASSWORD, auth

NUEVO = {"email": "nuevo@chrisco-pruebas.com", "full_name": "Nuevo Operador", "role": "operador"}


def alta(client, headers, **cambios):
    return client.post("/admin/personal", json={**NUEVO, **cambios}, headers=headers)


def usuario(db, email) -> User:
    db.expire_all()
    user = accounts.get_by_email(db, email)
    assert user is not None
    return user


def test_el_admin_da_de_alta_y_la_persona_crea_su_contrasena(client, admin_h, outbox, db) -> None:
    res = alta(client, admin_h)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["role"] == "operador" and body["is_active"] is True
    assert body["pendiente_invitacion"] is True

    correo = outbox.to(NUEVO["email"])[0]
    assert "operador" in correo.body and "aceptar-invitacion?token=" in correo.body
    token = correo.body.split("token=")[1].split()[0]

    # Antes de aceptar no puede entrar; después sí, ya con el rol que se le dio.
    assert client.post(
        "/auth/login", json={"email": NUEVO["email"], "password": PASSWORD}
    ).status_code in (401, 403)
    ok = client.post("/auth/accept-invite", json={"token": token, "password": PASSWORD})
    assert ok.status_code == 204
    sesion = client.post("/auth/login", json={"email": NUEVO["email"], "password": PASSWORD})
    assert sesion.status_code == 200
    yo = client.get("/auth/me", headers=auth(sesion.json())).json()
    assert yo["role"] == "operador"
    lista = client.get("/admin/personal", headers=admin_h).json()
    assert next(p for p in lista if p["email"] == NUEVO["email"])["pendiente_invitacion"] is False


@pytest.mark.parametrize(
    "cambios",
    [{"role": "cliente"}, {"role": "otro"}, {"email": "no-es-correo"}, {"full_name": "x"}],
)
def test_altas_invalidas(client, admin_h, cambios) -> None:
    assert alta(client, admin_h, **cambios).status_code == 422


def test_no_repite_correos_ni_con_clientes(client, admin_h, ventas_h, approved_owner) -> None:
    assert alta(client, admin_h, email="ventas@chrisco-pruebas.com").status_code == 409
    assert alta(client, admin_h, email=approved_owner["email"]).status_code == 409
    assert alta(client, admin_h, email="NUEVO@chrisco-pruebas.com").status_code == 201
    assert alta(client, admin_h).status_code == 409  # mismo correo en otra capitalización


def test_la_lista_solo_trae_personal(client, admin_h, ventas_h, approved_owner) -> None:
    lista = client.get("/admin/personal", headers=admin_h).json()
    assert {p["role"] for p in lista} == {"admin", "ventas"}
    assert approved_owner["email"] not in [p["email"] for p in lista]


def test_solo_el_admin_gestiona_al_personal(client, ventas_h, client_h) -> None:
    assert client.get("/admin/personal", headers=ventas_h).status_code == 403
    assert alta(client, ventas_h).status_code == 403
    assert client.get("/admin/personal", headers=client_h).status_code == 403
    assert client.get("/admin/personal").status_code == 401


def test_cambiar_el_rol_cierra_las_sesiones_de_esa_persona(client, admin_h, ventas_h, db) -> None:
    ventas = usuario(db, "ventas@chrisco-pruebas.com")
    res = client.put(f"/admin/personal/{ventas.id}", json={"role": "operador"}, headers=admin_h)
    assert res.status_code == 200 and res.json()["role"] == "operador"
    assert client.get("/auth/me", headers=ventas_h).status_code == 401  # su sesión ya no vale
    nueva = client.post("/auth/login", json={"email": ventas.email, "password": PASSWORD}).json()
    assert client.get("/auth/me", headers=auth(nueva)).json()["role"] == "operador"


def test_dar_de_baja_y_reactivar(client, admin_h, ventas_h, db) -> None:
    ventas = usuario(db, "ventas@chrisco-pruebas.com")
    url = f"/admin/personal/{ventas.id}"
    baja = client.put(url, json={"is_active": False}, headers=admin_h)
    assert baja.status_code == 200 and baja.json()["is_active"] is False
    assert client.get("/auth/me", headers=ventas_h).status_code == 401
    assert (
        client.post("/auth/login", json={"email": ventas.email, "password": PASSWORD}).status_code
        == 401
    )

    alta_de_nuevo = client.put(url, json={"is_active": True}, headers=admin_h)
    assert alta_de_nuevo.json()["is_active"] is True
    assert (
        client.post("/auth/login", json={"email": ventas.email, "password": PASSWORD}).status_code
        == 200
    )


def test_nadie_cambia_su_propio_rol_ni_se_da_de_baja(client, admin_h, db) -> None:
    yo = usuario(db, "admin@chrisco-pruebas.com")
    url = f"/admin/personal/{yo.id}"
    assert client.put(url, json={"is_active": False}, headers=admin_h).status_code == 409
    assert client.put(url, json={"role": "ventas"}, headers=admin_h).status_code == 409
    assert (
        client.put(url, json={"role": "admin"}, headers=admin_h).status_code == 200
    )  # sin cambios


def test_siempre_queda_un_administrador(client, admin_h, make_user, db) -> None:
    otro = make_user("otro-admin@chrisco-pruebas.com", Role.ADMIN)
    yo = usuario(db, "admin@chrisco-pruebas.com")
    # Con dos administradores uno puede dejar al otro...
    assert (
        client.put(
            f"/admin/personal/{otro.id}", json={"role": "ventas"}, headers=admin_h
        ).status_code
        == 200
    )
    # ...pero el que queda no se puede quitar (lo intenta alguien que ya no es admin, a nivel servicio).
    with SessionLocal() as session:
        intruso = accounts.get_by_email(session, "otro-admin@chrisco-pruebas.com")
        objetivo = personal.get_staff(session, yo.id)
        with pytest.raises(Conflict, match="al menos un administrador"):
            personal.update(session, intruso, objetivo, PersonalUpdate(is_active=False))
        with pytest.raises(Conflict, match="al menos un administrador"):
            personal.update(session, intruso, objetivo, PersonalUpdate(role="ventas"))


def test_dos_administradores_no_se_quitan_mutuamente(client, admin_h, make_user, db) -> None:
    """Cada uno intenta dar de baja al otro a la vez: solo uno puede lograrlo."""
    a = usuario(db, "admin@chrisco-pruebas.com")
    b = make_user("otro-admin@chrisco-pruebas.com", Role.ADMIN)
    barrera = threading.Barrier(2)
    resultados: list[str] = []

    def quitar(actor_id: uuid.UUID, objetivo_id: uuid.UUID) -> None:
        with SessionLocal() as session:
            actor = session.get(User, actor_id)
            objetivo = personal.get_staff(session, objetivo_id)
            barrera.wait()
            try:
                personal.update(session, actor, objetivo, PersonalUpdate(is_active=False))
                resultados.append("ok")
            except Conflict:
                resultados.append("conflicto")

    hilos = [
        threading.Thread(target=quitar, args=(a.id, b.id)),
        threading.Thread(target=quitar, args=(b.id, a.id)),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(resultados) == ["conflicto", "ok"]
    db.expire_all()
    assert personal.get_staff(db, a.id).is_active != personal.get_staff(db, b.id).is_active


def test_reenviar_la_invitacion(client, admin_h, ventas_h, outbox, db) -> None:
    creado = alta(client, admin_h).json()
    outbox.clear()
    res = client.post(f"/admin/personal/{creado['id']}/invitacion", headers=admin_h)
    assert res.status_code == 204
    assert len(outbox.to(NUEVO["email"])) == 1

    ventas = usuario(db, "ventas@chrisco-pruebas.com")  # ya tiene contraseña
    assert (
        client.post(f"/admin/personal/{ventas.id}/invitacion", headers=admin_h).status_code == 409
    )
    client.put(f"/admin/personal/{creado['id']}", json={"is_active": False}, headers=admin_h)
    assert (
        client.post(f"/admin/personal/{creado['id']}/invitacion", headers=admin_h).status_code
        == 409
    )


def test_no_se_gestionan_clientes_por_aqui(client, admin_h, approved_owner, db) -> None:
    cliente = usuario(db, approved_owner["email"])
    assert (
        client.put(
            f"/admin/personal/{cliente.id}", json={"is_active": False}, headers=admin_h
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/admin/personal/{uuid.uuid4()}", json={"is_active": False}, headers=admin_h
        ).status_code
        == 404
    )

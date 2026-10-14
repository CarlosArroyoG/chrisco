from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.api.deps import require_roles
from app.main import app
from app.models.user import Role
from tests.conftest import PASSWORD

# Ruta de prueba solo para ejercitar require_roles (las rutas reales llegan en fases siguientes).
_probe = APIRouter()


@_probe.get("/_probe/admin-only", dependencies=[Depends(require_roles(Role.ADMIN))])
def _admin_only() -> dict[str, bool]:
    return {"ok": True}


app.include_router(_probe)


def auth(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_login_ok_y_me(client, make_user, login) -> None:
    make_user()
    res = client.get("/auth/me", headers=auth(login()))
    assert res.status_code == 200
    assert res.json()["email"] == "admin@chrisco-pruebas.com"
    assert res.json()["role"] == "admin"
    assert "password" not in res.text


def test_login_es_insensible_a_mayusculas_en_correo(client, make_user) -> None:
    make_user()
    res = client.post(
        "/auth/login", json={"email": "ADMIN@chrisco-pruebas.com", "password": PASSWORD}
    )
    assert res.status_code == 200


def test_login_password_incorrecta(client, make_user) -> None:
    make_user()
    res = client.post(
        "/auth/login", json={"email": "admin@chrisco-pruebas.com", "password": "mala"}
    )
    assert res.status_code == 401


def test_login_usuario_inexistente_da_el_mismo_error(client, make_user) -> None:
    make_user()
    bad_pw = client.post(
        "/auth/login", json={"email": "admin@chrisco-pruebas.com", "password": "mala"}
    )
    no_user = client.post(
        "/auth/login", json={"email": "nadie@chrisco-pruebas.com", "password": "mala"}
    )
    assert no_user.status_code == bad_pw.status_code == 401
    assert no_user.json() == bad_pw.json()


def test_usuario_inactivo_no_puede_entrar(client, make_user) -> None:
    make_user(active=False)
    res = client.post(
        "/auth/login", json={"email": "admin@chrisco-pruebas.com", "password": PASSWORD}
    )
    assert res.status_code == 401


def test_me_sin_token(client) -> None:
    assert client.get("/auth/me").status_code == 401


def test_me_con_token_basura(client) -> None:
    res = client.get("/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert res.status_code == 401


def test_refresh_token_no_sirve_como_access(client, make_user, login) -> None:
    make_user()
    tokens = login()
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert res.status_code == 401


def test_access_token_no_sirve_como_refresh(client, make_user, login) -> None:
    make_user()
    res = client.post("/auth/refresh", json={"refresh_token": login()["access_token"]})
    assert res.status_code == 401


def test_refresh_ok(client, make_user, login) -> None:
    make_user()
    res = client.post("/auth/refresh", json={"refresh_token": login()["refresh_token"]})
    assert res.status_code == 200
    assert client.get("/auth/me", headers=auth(res.json())).status_code == 200


def test_logout_all_invalida_tokens(client, make_user, login) -> None:
    make_user()
    tokens = login()
    assert client.post("/auth/logout-all", headers=auth(tokens)).status_code == 204
    assert client.get("/auth/me", headers=auth(tokens)).status_code == 401
    assert (
        client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 401
    )


def test_desactivar_usuario_invalida_sesion(client, make_user, login, db) -> None:
    user = make_user()
    tokens = login()
    user.is_active = False
    db.commit()
    assert client.get("/auth/me", headers=auth(tokens)).status_code == 401


def test_roles_admin_pasa_y_cliente_recibe_403(client, make_user, login) -> None:
    make_user("admin@chrisco-pruebas.com", Role.ADMIN)
    make_user("cliente@chrisco-pruebas.com", Role.CLIENTE)
    assert (
        client.get(
            "/_probe/admin-only", headers=auth(login("admin@chrisco-pruebas.com"))
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/_probe/admin-only", headers=auth(login("cliente@chrisco-pruebas.com"))
        ).status_code
        == 403
    )
    assert client.get("/_probe/admin-only").status_code == 401

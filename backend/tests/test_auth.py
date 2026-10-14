from fastapi.testclient import TestClient

from app.core.limiter import limiter
from app.core.security import create_token
from app.models.user import Role
from tests.conftest import PASSWORD, auth, token_from


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
        "/auth/login", json={"email": "ADMIN@Chrisco-Pruebas.com", "password": PASSWORD}
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


def test_token_de_correo_no_sirve_como_sesion(client, make_user) -> None:
    user = make_user()
    for token_type in ("verify_email", "invite", "reset_password"):
        token = create_token(user.id, user.token_version, token_type)
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401, token_type


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
    refresh = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401


def test_desactivar_usuario_invalida_sesion(client, make_user, login, db) -> None:
    user = make_user()
    tokens = login()
    user.is_active = False
    db.commit()
    assert client.get("/auth/me", headers=auth(tokens)).status_code == 401


def test_roles_admin_pasa_y_cliente_recibe_403(client, make_user, approved_owner, login) -> None:
    make_user("admin@chrisco-pruebas.com", Role.ADMIN)
    admin = auth(login("admin@chrisco-pruebas.com"))
    cliente = auth(login(**approved_owner))
    assert client.get("/_probe/admin-only", headers=admin).status_code == 200
    assert client.get("/_probe/admin-only", headers=cliente).status_code == 403
    assert client.get("/_probe/admin-only").status_code == 401


def test_limite_de_intentos_de_login(client, make_user) -> None:
    make_user()
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [
            client.post(
                "/auth/login", json={"email": "admin@chrisco-pruebas.com", "password": "mala"}
            ).status_code
            for _ in range(12)
        ]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:10] == [401] * 10
    assert 429 in codes[10:]


def test_olvide_mi_contrasena_no_revela_si_existe(client, make_user, outbox) -> None:
    make_user()
    assert client.post("/auth/forgot-password", json={"email": "nadie@x.com"}).status_code == 204
    assert not outbox
    res = client.post("/auth/forgot-password", json={"email": "admin@chrisco-pruebas.com"})
    assert res.status_code == 204
    assert len(outbox.to("admin@chrisco-pruebas.com")) == 1


def test_restablecer_contrasena(client, make_user, login, outbox) -> None:
    make_user()
    old_tokens = login()
    client.post("/auth/forgot-password", json={"email": "admin@chrisco-pruebas.com"})
    token = token_from(outbox[0])

    nueva = "otra-contraseña-larga-456"
    res = client.post("/auth/reset-password", json={"token": token, "password": nueva})
    assert res.status_code == 204

    assert login(password=nueva)["access_token"]
    mala = client.post(
        "/auth/login", json={"email": "admin@chrisco-pruebas.com", "password": PASSWORD}
    )
    assert mala.status_code == 401
    # Cierra las sesiones anteriores y el enlace no se puede reutilizar.
    assert client.get("/auth/me", headers=auth(old_tokens)).status_code == 401
    again = client.post("/auth/reset-password", json={"token": token, "password": nueva})
    assert again.status_code == 422


def test_restablecer_exige_contrasena_larga(client, make_user, outbox) -> None:
    make_user()
    client.post("/auth/forgot-password", json={"email": "admin@chrisco-pruebas.com"})
    res = client.post(
        "/auth/reset-password", json={"token": token_from(outbox[0]), "password": "corta"}
    )
    assert res.status_code == 422

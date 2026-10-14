from tests.conftest import CATEGORIA, auth


def test_crear_y_listar_categorias(client, admin_h, ventas_h) -> None:
    res = client.post("/admin/categorias", json=CATEGORIA, headers=admin_h)
    assert res.status_code == 201
    assert [f["key"] for f in res.json()["spec_fields"]][0] == "peso_kg"

    for headers in (admin_h, ventas_h):
        listado = client.get("/admin/categorias", headers=headers).json()
        assert listado[0]["nombre"] == "Pavimentadora" and listado[0]["equipos_count"] == 0


def test_solo_el_admin_modifica_categorias(client, ventas_h, categoria, client_h) -> None:
    assert client.post("/admin/categorias", json=CATEGORIA, headers=ventas_h).status_code == 403
    assert client.post("/admin/categorias", json=CATEGORIA, headers=client_h).status_code == 403
    assert client.post("/admin/categorias", json=CATEGORIA).status_code == 401
    url = f"/admin/categorias/{categoria['id']}"
    assert client.put(url, json=CATEGORIA, headers=ventas_h).status_code == 403
    assert client.delete(url, headers=ventas_h).status_code == 403


def test_nombre_unico_sin_importar_mayusculas(client, admin_h, categoria) -> None:
    res = client.post(
        "/admin/categorias", json={**CATEGORIA, "nombre": "pavimentadora"}, headers=admin_h
    )
    assert res.status_code == 409


def test_editar_categoria(client, admin_h, categoria) -> None:
    body = {"nombre": "Pavimentadora de asfalto", "spec_fields": []}
    res = client.put(f"/admin/categorias/{categoria['id']}", json=body, headers=admin_h)
    assert res.status_code == 200
    assert res.json()["nombre"] == "Pavimentadora de asfalto" and res.json()["spec_fields"] == []


def test_renombrar_a_un_nombre_ocupado(client, admin_h, categoria) -> None:
    otra = client.post(
        "/admin/categorias", json={"nombre": "Grúa", "spec_fields": []}, headers=admin_h
    ).json()
    res = client.put(
        f"/admin/categorias/{otra['id']}", json={"nombre": "Pavimentadora"}, headers=admin_h
    )
    assert res.status_code == 409
    # Guardarse con su propio nombre no es conflicto.
    assert (
        client.put(
            f"/admin/categorias/{otra['id']}", json={"nombre": "Grúa"}, headers=admin_h
        ).status_code
        == 200
    )


def test_definicion_de_campos_invalida(client, admin_h) -> None:
    body = {
        "nombre": "Grúa",
        "spec_fields": [{"key": "x", "label": "X", "type": "select", "options": ["A"]}],
    }
    assert client.post("/admin/categorias", json=body, headers=admin_h).status_code == 422


def test_eliminar_categoria_sin_equipos(client, admin_h, categoria) -> None:
    assert client.delete(f"/admin/categorias/{categoria['id']}", headers=admin_h).status_code == 204
    assert client.get("/admin/categorias", headers=admin_h).json() == []


def test_no_se_elimina_una_categoria_con_equipos(client, admin_h, categoria, make_equipo) -> None:
    make_equipo()
    res = client.delete(f"/admin/categorias/{categoria['id']}", headers=admin_h)
    assert res.status_code == 409 and "1 equipo" in res.json()["detail"]
    assert client.get("/admin/categorias", headers=admin_h).json()[0]["equipos_count"] == 1


def test_categoria_inexistente(client, admin_h) -> None:
    res = client.put(
        "/admin/categorias/00000000-0000-0000-0000-000000000000", json=CATEGORIA, headers=admin_h
    )
    assert res.status_code == 404


def test_lectura_publica_para_el_catalogo(
    client, categoria, client_h, ventas_h, register, verify_email, login
) -> None:
    for headers in (client_h, ventas_h):
        assert client.get("/categorias", headers=headers).json()[0]["nombre"] == "Pavimentadora"
    # Una empresa que aún no se aprueba no ve el catálogo.
    register(rfc="OTR020202XY9", email="otro@otra-empresa.com")
    verify_email("otro@otra-empresa.com")
    pendiente = auth(login("otro@otra-empresa.com"))
    assert client.get("/categorias", headers=pendiente).status_code == 403
    assert client.get("/categorias").status_code == 401

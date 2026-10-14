import uuid

from tests.conftest import auth, equipo_payload


def test_el_cliente_aprobado_ve_solo_equipos_activos(
    client, client_h, admin_h, categoria, make_equipo
) -> None:
    activo = make_equipo()
    en_mantenimiento = make_equipo()
    dado_de_baja = make_equipo()
    for equipo, status in ((en_mantenimiento, "mantenimiento"), (dado_de_baja, "baja")):
        body = equipo_payload(categoria["id"], int(equipo["codigo"][-3:]), status=status)
        client.put(f"/admin/equipos/{equipo['id']}", json=body, headers=admin_h)

    catalogo = client.get("/equipos", headers=client_h).json()
    assert catalogo["total"] == 1 and catalogo["items"][0]["id"] == activo["id"]
    assert client.get(f"/equipos/{activo['id']}", headers=client_h).status_code == 200
    for oculto in (en_mantenimiento, dado_de_baja):
        assert client.get(f"/equipos/{oculto['id']}", headers=client_h).status_code == 404


def test_el_cliente_no_ve_datos_internos(client, client_h, make_equipo) -> None:
    equipo = make_equipo(notas="Cambiar bandas pronto", numero_serie="SERIE-SECRETA")
    item = client.get(f"/equipos/{equipo['id']}", headers=client_h).json()
    assert item["codigo"] == "EQ-001" and item["nombre"] == "Pavimentadora 1"
    assert item["tarifa_hora"] == 3400
    for privado in ("numero_serie", "horometro", "notas", "status", "specs_raw"):
        assert privado not in item
    assert "SERIE-SECRETA" not in str(item) and "bandas" not in str(item)


def test_las_especificaciones_llegan_listas_para_mostrar(client, client_h, make_equipo) -> None:
    equipo = make_equipo()
    specs = client.get(f"/equipos/{equipo['id']}", headers=client_h).json()["specs"]
    assert specs == [
        {"label": "Peso", "value": "18000", "unit": "kg"},
        {"label": "Motor", "value": "Cummins 6.7", "unit": None},
        {"label": "Combustible", "value": "Diésel", "unit": None},
        {"label": "Con orugas", "value": "Sí", "unit": None},
    ]


def test_el_personal_tambien_ve_el_catalogo(client, ventas_h, admin_h, make_equipo) -> None:
    make_equipo()
    for headers in (ventas_h, admin_h):
        assert client.get("/equipos", headers=headers).json()["total"] == 1


def test_sin_acceso_si_la_empresa_no_esta_aprobada(
    client, register, verify_email, login, make_equipo
) -> None:
    make_equipo()
    register()
    verify_email("titular@constructora-prueba.com")
    pendiente = auth(login("titular@constructora-prueba.com"))
    assert client.get("/equipos", headers=pendiente).status_code == 403
    assert client.get(f"/equipos/{uuid.uuid4()}", headers=pendiente).status_code == 403
    assert client.get("/equipos").status_code == 401


def test_buscar_y_filtrar_en_el_catalogo(client, client_h, categoria, admin_h, make_equipo) -> None:
    make_equipo(marca="Caterpillar", nombre="Excavadora 320")
    make_equipo()
    otra = client.post(
        "/admin/categorias", json={"nombre": "Grúa", "spec_fields": []}, headers=admin_h
    ).json()
    client.post("/admin/equipos", json=equipo_payload(otra["id"], 7, specs={}), headers=admin_h)

    assert client.get("/equipos?q=excavadora", headers=client_h).json()["total"] == 1
    assert client.get(f"/equipos?categoria_id={otra['id']}", headers=client_h).json()["total"] == 1
    assert client.get("/equipos?limit=1", headers=client_h).json()["total"] == 3
    assert len(client.get("/equipos?limit=1", headers=client_h).json()["items"]) == 1


def test_el_catalogo_incluye_las_fotos(client, client_h, admin_h, make_equipo) -> None:
    import io

    from PIL import Image

    equipo = make_equipo()
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")
    client.post(
        f"/admin/equipos/{equipo['id']}/fotos",
        files={"foto": ("a.png", buf.getvalue(), "image/png")},
        headers=admin_h,
    )
    fotos = client.get(f"/equipos/{equipo['id']}", headers=client_h).json()["fotos"]
    assert (
        len(fotos) == 1 and client.get(f"/equipos/fotos/{fotos[0]['id']}/thumb").status_code == 200
    )
    assert client.get(f"/equipos/fotos/{fotos[0]['id']}/enorme").status_code == 422

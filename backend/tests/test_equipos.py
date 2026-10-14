import io
import uuid

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models.equipo import Equipo
from tests.conftest import equipo_payload, uploads_count


def png(width: int = 64, height: int = 48, fmt: str = "PNG") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), (200, 120, 30)).save(out, format=fmt)
    return out.getvalue()


def jpeg_with_exif() -> bytes:
    image = Image.new("RGB", (80, 60), (10, 20, 30))
    exif = Image.Exif()
    exif[0x010F] = "Camara Secreta"  # fabricante
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def upload(client, headers, equipo_id, data, name="foto.png"):
    return client.post(
        f"/admin/equipos/{equipo_id}/fotos",
        files={"foto": (name, data, "image/png")},
        headers=headers,
    )


# ---------------------------------------------------------------- alta y edición


def test_crear_equipo(client, admin_h, categoria) -> None:
    body = equipo_payload(categoria["id"], codigo="eq-100", horometro=2400.5)
    res = client.post("/admin/equipos", json=body, headers=admin_h)
    assert res.status_code == 201
    data = res.json()
    assert data["codigo"] == "EQ-100"  # se normaliza a mayúsculas
    assert data["status"] == "activo" and data["categoria_nombre"] == "Pavimentadora"
    assert data["tarifa_hora"] == 3400 and data["horometro"] == 2400.5  # números, no cadenas
    assert data["tarifa_dia"] is None and data["fotos"] == []
    assert data["patio"] == "Patio Toluca CHRISCO"


def test_solo_el_admin_crea_y_edita(client, ventas_h, client_h, categoria, make_equipo) -> None:
    body = equipo_payload(categoria["id"], 9)
    assert client.post("/admin/equipos", json=body, headers=ventas_h).status_code == 403
    assert client.post("/admin/equipos", json=body, headers=client_h).status_code == 403
    assert client.post("/admin/equipos", json=body).status_code == 401
    equipo = make_equipo()
    assert (
        client.put(f"/admin/equipos/{equipo['id']}", json=body, headers=ventas_h).status_code == 403
    )
    # El personal de ventas sí puede consultar.
    assert client.get(f"/admin/equipos/{equipo['id']}", headers=ventas_h).status_code == 200
    assert client.get("/admin/equipos", headers=client_h).status_code == 403


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"tarifa_hora": None}, "tarifa por hora, por día o ambas"),
        ({"tarifa_hora": 0}, ""),
        ({"tarifa_hora": -5}, ""),
        ({"tarifa_hora": 3400.123}, ""),
        ({"codigo": "x"}, "código"),
        ({"codigo": "con espacios"}, "código"),
        ({"anio": 1900}, ""),
        ({"horometro": -1}, ""),
        ({"nombre": "x"}, ""),
    ],
)
def test_validaciones_de_alta(client, admin_h, categoria, override, fragment) -> None:
    body = equipo_payload(categoria["id"], **override)
    res = client.post("/admin/equipos", json=body, headers=admin_h)
    assert res.status_code == 422, res.text
    assert fragment in res.text


def test_categoria_con_formato_invalido(client, admin_h, categoria) -> None:
    body = {**equipo_payload(categoria["id"]), "categoria_id": "no-es-uuid"}
    assert client.post("/admin/equipos", json=body, headers=admin_h).status_code == 422


def test_basta_con_tarifa_por_dia(client, admin_h, categoria) -> None:
    body = equipo_payload(categoria["id"], tarifa_hora=None, tarifa_dia=25000)
    assert client.post("/admin/equipos", json=body, headers=admin_h).status_code == 201


def test_categoria_inexistente_al_crear(client, admin_h) -> None:
    body = equipo_payload(str(uuid.uuid4()))
    assert client.post("/admin/equipos", json=body, headers=admin_h).status_code == 404


def test_codigo_y_serie_unicos(client, admin_h, categoria, make_equipo) -> None:
    make_equipo()  # EQ-001 / SN-0001
    dup_code = equipo_payload(categoria["id"], 2, codigo="eq-001")
    res = client.post("/admin/equipos", json=dup_code, headers=admin_h)
    assert res.status_code == 409 and "código" in res.json()["detail"]
    dup_serial = equipo_payload(categoria["id"], 2, numero_serie="SN-0001")
    res = client.post("/admin/equipos", json=dup_serial, headers=admin_h)
    assert res.status_code == 409 and "número de serie" in res.json()["detail"]


def test_especificaciones_se_validan_contra_la_categoria(client, admin_h, categoria) -> None:
    def post(specs):
        return client.post(
            "/admin/equipos", json=equipo_payload(categoria["id"], specs=specs), headers=admin_h
        )

    assert post({}).status_code == 422  # «Peso» es obligatorio
    assert post({"peso_kg": "mucho"}).status_code == 422
    assert post({"peso_kg": 1, "color": "rojo"}).status_code == 422
    assert post({"peso_kg": 1, "combustible": "Agua"}).status_code == 422
    assert post({"peso_kg": 1}).status_code == 201


def test_editar_equipo_y_cambiar_su_estado(client, admin_h, categoria, make_equipo) -> None:
    equipo = make_equipo()
    body = equipo_payload(
        categoria["id"], 1, nombre="Pavimentadora renovada", status="mantenimiento"
    )
    res = client.put(f"/admin/equipos/{equipo['id']}", json=body, headers=admin_h)
    assert res.status_code == 200
    assert (
        res.json()["nombre"] == "Pavimentadora renovada" and res.json()["status"] == "mantenimiento"
    )
    baja = {**body, "status": "baja"}
    assert (
        client.put(f"/admin/equipos/{equipo['id']}", json=baja, headers=admin_h).json()["status"]
        == "baja"
    )


def test_editar_conservando_su_propio_codigo_no_es_conflicto(
    client, admin_h, categoria, make_equipo
) -> None:
    equipo = make_equipo()
    body = equipo_payload(categoria["id"], 1, marca="Otra marca")
    assert (
        client.put(f"/admin/equipos/{equipo['id']}", json=body, headers=admin_h).status_code == 200
    )


def test_editar_hacia_el_codigo_de_otro_equipo(client, admin_h, categoria, make_equipo) -> None:
    make_equipo()
    segundo = make_equipo()
    body = equipo_payload(categoria["id"], 2, codigo="EQ-001")
    assert (
        client.put(f"/admin/equipos/{segundo['id']}", json=body, headers=admin_h).status_code == 409
    )


def test_equipo_inexistente(client, admin_h) -> None:
    assert client.get(f"/admin/equipos/{uuid.uuid4()}", headers=admin_h).status_code == 404


# ---------------------------------------------------------------- búsqueda y paginación


def test_buscar_filtrar_y_paginar(client, admin_h, categoria, make_equipo) -> None:
    for n in range(5):
        make_equipo(marca="Vögele" if n < 3 else "Caterpillar")
    listado = client.get("/admin/equipos?limit=2&offset=0", headers=admin_h).json()
    assert listado["total"] == 5 and [e["codigo"] for e in listado["items"]] == ["EQ-001", "EQ-002"]
    siguiente = client.get("/admin/equipos?limit=2&offset=4", headers=admin_h).json()
    assert [e["codigo"] for e in siguiente["items"]] == ["EQ-005"]

    cat = client.get("/admin/equipos?q=caterpillar", headers=admin_h).json()
    assert cat["total"] == 2
    assert client.get("/admin/equipos?q=sn-0003", headers=admin_h).json()["total"] == 1
    assert (
        client.get(f"/admin/equipos?categoria_id={categoria['id']}", headers=admin_h).json()[
            "total"
        ]
        == 5
    )
    assert (
        client.get(f"/admin/equipos?categoria_id={uuid.uuid4()}", headers=admin_h).json()["total"]
        == 0
    )
    assert client.get("/admin/equipos?status_filter=baja", headers=admin_h).json()["total"] == 0
    assert client.get("/admin/equipos?limit=0", headers=admin_h).status_code == 422
    assert client.get("/admin/equipos?limit=500", headers=admin_h).status_code == 422


# ---------------------------------------------------------------- restricciones de la base de datos


@pytest.mark.parametrize(
    "assignment",
    ["tarifa_hora = NULL, tarifa_dia = NULL", "tarifa_dia = -1", "horometro = -0.1", "anio = 1800"],
)
def test_la_base_de_datos_protege_los_datos_del_equipo(db, make_equipo, assignment) -> None:
    equipo = make_equipo()
    with pytest.raises(IntegrityError):
        db.execute(text(f"UPDATE equipos SET {assignment} WHERE id = :id"), {"id": equipo["id"]})
    db.rollback()


# ---------------------------------------------------------------- fotos


def test_subir_foto_genera_dos_tamanos_sin_metadatos(client, admin_h, make_equipo) -> None:
    equipo = make_equipo()
    res = upload(client, admin_h, equipo["id"], jpeg_with_exif(), "camara.jpg")
    assert res.status_code == 201
    foto_id = res.json()["id"]
    assert uploads_count("jpg") == 2

    for size in ("thumb", "full"):
        img = client.get(f"/equipos/fotos/{foto_id}/{size}")  # sin sesión: es material de catálogo
        assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
        assert "immutable" in img.headers["cache-control"]
        assert not Image.open(io.BytesIO(img.content)).getexif()  # se descartaron los metadatos
    detalle = client.get(f"/admin/equipos/{equipo['id']}", headers=admin_h).json()
    assert [f["id"] for f in detalle["fotos"]] == [foto_id]


def test_las_fotos_grandes_se_reducen(client, admin_h, make_equipo) -> None:
    equipo = make_equipo()
    foto_id = upload(client, admin_h, equipo["id"], png(3200, 2400), "grande.png").json()["id"]
    full = Image.open(io.BytesIO(client.get(f"/equipos/fotos/{foto_id}/full").content))
    thumb = Image.open(io.BytesIO(client.get(f"/equipos/fotos/{foto_id}/thumb").content))
    assert max(full.size) == 1600 and max(thumb.size) == 480


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        pytest.param(b"esto no es una imagen", "no es una imagen válida", id="texto"),
        pytest.param(png(fmt="GIF"), "JPG, PNG o WebP", id="gif"),
        pytest.param(png(fmt="BMP"), "JPG, PNG o WebP", id="bmp"),
        pytest.param(b"%PDF-1.4 falso", "no es una imagen válida", id="pdf"),
        pytest.param(png(7000, 7000), "demasiado grande", id="mas-de-40-megapixeles"),
        pytest.param(
            b"\x89PNG" + b"0" * (get_settings().max_upload_mb * 1024 * 1024),
            "supera el máximo",
            id="mas-de-5-mb",
        ),
    ],
)
def test_archivos_que_no_son_fotos_validas(client, admin_h, make_equipo, data, fragment) -> None:
    equipo = make_equipo()
    res = upload(client, admin_h, equipo["id"], data)
    assert res.status_code == 422 and fragment in res.json()["detail"]
    assert uploads_count("jpg") == 0


def test_maximo_de_fotos_por_equipo(client, admin_h, make_equipo) -> None:
    equipo = make_equipo()
    for _ in range(10):
        assert upload(client, admin_h, equipo["id"], png()).status_code == 201
    assert upload(client, admin_h, equipo["id"], png()).status_code == 409


def test_eliminar_foto_borra_los_archivos(client, admin_h, make_equipo) -> None:
    equipo = make_equipo()
    foto_id = upload(client, admin_h, equipo["id"], png()).json()["id"]
    assert (
        client.delete(f"/admin/equipos/{equipo['id']}/fotos/{foto_id}", headers=admin_h).status_code
        == 204
    )
    assert uploads_count("jpg") == 0
    assert client.get(f"/equipos/fotos/{foto_id}/thumb").status_code == 404
    assert (
        client.delete(f"/admin/equipos/{equipo['id']}/fotos/{foto_id}", headers=admin_h).status_code
        == 404
    )


def test_las_posiciones_de_las_fotos_son_consecutivas(client, admin_h, make_equipo) -> None:
    equipo = make_equipo()
    ids = [upload(client, admin_h, equipo["id"], png()).json()["id"] for _ in range(3)]
    client.delete(f"/admin/equipos/{equipo['id']}/fotos/{ids[0]}", headers=admin_h)
    nueva = upload(client, admin_h, equipo["id"], png()).json()
    fotos = client.get(f"/admin/equipos/{equipo['id']}", headers=admin_h).json()["fotos"]
    assert [f["id"] for f in fotos] == [ids[1], ids[2], nueva["id"]]
    assert [f["position"] for f in fotos] == sorted(f["position"] for f in fotos)


def test_solo_el_admin_sube_fotos(client, ventas_h, admin_h, make_equipo) -> None:
    equipo = make_equipo()
    assert upload(client, ventas_h, equipo["id"], png()).status_code == 403
    foto_id = upload(client, admin_h, equipo["id"], png()).json()["id"]
    assert (
        client.delete(
            f"/admin/equipos/{equipo['id']}/fotos/{foto_id}", headers=ventas_h
        ).status_code
        == 403
    )


def test_borrar_el_equipo_borra_sus_fotos_de_la_base(db, client, admin_h, make_equipo) -> None:
    equipo = make_equipo()
    upload(client, admin_h, equipo["id"], png())
    db.delete(db.get(Equipo, uuid.UUID(equipo["id"])))
    db.commit()
    assert db.execute(text("SELECT count(*) FROM equipo_fotos")).scalar() == 0

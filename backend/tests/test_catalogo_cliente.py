"""Catálogo visual del cliente: descripción, situación del equipo, filtro y su renta abierta."""

import io
from datetime import UTC, datetime, timedelta

from PIL import Image

from tests.rentas_helpers import apartar, cotizar, pedir


def foto_png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (60, 40), (200, 90, 10)).save(out, format="PNG")
    return out.getvalue()


def catalogo(client, headers, **params):
    res = client.get("/equipos", params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def item(client, headers, equipo_id):
    return next(e for e in catalogo(client, headers)["items"] if e["id"] == equipo_id)


def test_la_descripcion_publica_llega_al_catalogo_y_las_notas_no(
    client, client_h, admin_h, make_equipo
) -> None:
    e = make_equipo(
        descripcion="Excavadora de 20 t, ideal para zanjas.", notas="Se atora la palanca"
    )
    visto = item(client, client_h, e["id"])
    assert visto["descripcion"] == "Excavadora de 20 t, ideal para zanjas."
    assert "notas" not in visto
    assert (
        client.get(f"/equipos/{e['id']}", headers=client_h).json()["descripcion"]
        == visto["descripcion"]
    )
    # El personal la ve y puede editarla.
    completo = client.get(f"/admin/equipos/{e['id']}", headers=admin_h).json()
    assert (
        completo["descripcion"] == visto["descripcion"]
        and completo["notas"] == "Se atora la palanca"
    )


def test_la_descripcion_es_opcional_y_tiene_limite(client, admin_h, make_equipo) -> None:
    assert make_equipo()["descripcion"] is None
    larga = "x" * 2001
    res = client.post(
        "/admin/equipos",
        json={
            "codigo": "LARGA-1",
            "categoria_id": make_equipo()["categoria_id"],
            "nombre": "Equipo largo",
            "marca": "M",
            "modelo": "M1",
            "numero_serie": "SN-LARGA",
            "tarifa_hora": 100,
            "descripcion": larga,
        },
        headers=admin_h,
    )
    assert res.status_code == 422


def test_situacion_actual_del_equipo(client, client_h, admin_h, make_equipo) -> None:
    e = make_equipo()
    assert item(client, client_h, e["id"])["situacion"] == "libre"
    ahora = datetime.now(UTC)
    client.post(
        f"/admin/equipos/{e['id']}/bloqueos",
        json={
            "tipo": "manual",
            "motivo": "Prueba",
            "desde": (ahora - timedelta(hours=1)).isoformat(),
            "hasta": (ahora + timedelta(days=2)).isoformat(),
        },
        headers=admin_h,
    )
    assert item(client, client_h, e["id"])["situacion"] == "bloqueado"


def test_filtrar_por_situacion_y_paginar(client, client_h, admin_h, make_equipo) -> None:
    libres = [make_equipo() for _ in range(3)]
    ocupado = make_equipo()
    ahora = datetime.now(UTC)
    client.post(
        f"/admin/equipos/{ocupado['id']}/bloqueos",
        json={
            "tipo": "manual",
            "motivo": "Prueba",
            "desde": (ahora - timedelta(hours=1)).isoformat(),
            "hasta": (ahora + timedelta(days=1)).isoformat(),
        },
        headers=admin_h,
    )
    todos_libres = catalogo(client, client_h, situacion="libre")
    assert todos_libres["total"] == 3
    assert {e["id"] for e in todos_libres["items"]} == {e["id"] for e in libres}
    pagina = catalogo(client, client_h, situacion="libre", limit=2, offset=2)
    assert pagina["total"] == 3 and len(pagina["items"]) == 1
    assert [e["id"] for e in catalogo(client, client_h, situacion="bloqueado")["items"]] == [
        ocupado["id"]
    ]
    assert catalogo(client, client_h, situacion="rentado")["items"] == []
    assert client.get("/equipos?situacion=inventada", headers=client_h).status_code == 422


def test_mi_renta_sigue_la_etapa_de_la_renta(
    client, client_h, otra_empresa_h, admin_h, ventas_h, make_equipo
) -> None:
    e = make_equipo()
    assert item(client, client_h, e["id"])["mi_renta"] is None

    renta = pedir(client, client_h, e["id"]).json()
    mia = item(client, client_h, e["id"])["mi_renta"]
    assert mia == {"id": renta["id"], "folio": renta["folio"], "estado": "solicitada"}
    assert (
        client.get(f"/equipos/{e['id']}", headers=client_h).json()["mi_renta"]["estado"]
        == "solicitada"
    )

    # Para otra empresa y para el personal no hay «mi renta».
    assert item(client, otra_empresa_h, e["id"])["mi_renta"] is None
    assert item(client, admin_h, e["id"])["mi_renta"] is None

    cotizar(client, ventas_h, renta["id"])
    assert item(client, client_h, e["id"])["mi_renta"]["estado"] == "cotizada"
    client.post(f"/rentas/{renta['id']}/cotizacion/aceptar", headers=client_h)
    assert item(client, client_h, e["id"])["mi_renta"]["estado"] == "apartada"


def test_una_renta_cancelada_ya_no_es_mi_renta(client, client_h, make_equipo) -> None:
    e = make_equipo()
    renta = pedir(client, client_h, e["id"]).json()
    client.post(f"/rentas/{renta['id']}/cancelar", headers=client_h)
    assert item(client, client_h, e["id"])["mi_renta"] is None


def test_la_renta_trae_la_foto_del_equipo_y_su_total(
    client, client_h, admin_h, ventas_h, make_equipo
) -> None:
    e = make_equipo()
    foto = client.post(
        f"/admin/equipos/{e['id']}/fotos",
        files={"foto": ("f.png", foto_png(), "image/png")},
        headers=admin_h,
    ).json()
    renta = pedir(client, client_h, e["id"]).json()
    assert renta["equipo_foto_id"] == foto["id"] and renta["total"] is None

    cotizar(client, ventas_h, renta["id"])
    con_total = client.get(f"/rentas/{renta['id']}", headers=client_h).json()
    assert con_total["total"] == 36772
    lista = client.get("/rentas", headers=client_h).json()["items"]
    assert lista[0]["equipo_foto_id"] == foto["id"] and lista[0]["total"] == 36772


def test_apartar_helper_sigue_funcionando(client, client_h, ventas_h, make_equipo) -> None:
    renta = apartar(client, client_h, ventas_h, make_equipo()["id"])
    assert renta["estado"] == "apartada" and renta["total"] == 36772


def test_un_mantenimiento_no_se_revela_al_cliente(client, client_h, admin_h, make_equipo) -> None:
    e = make_equipo()
    ahora = datetime.now(UTC)
    client.post(
        f"/admin/equipos/{e['id']}/bloqueos",
        json={
            "tipo": "mantenimiento",
            "motivo": "Cambio de motor",
            "desde": (ahora - timedelta(hours=1)).isoformat(),
            "hasta": (ahora + timedelta(days=2)).isoformat(),
        },
        headers=admin_h,
    )
    # El personal sabe que está en mantenimiento; el cliente solo ve que no está disponible.
    staff = client.get(f"/admin/equipos/{e['id']}", headers=admin_h).json()
    assert staff["estado_actual"] == "mantenimiento"
    assert item(client, client_h, e["id"])["situacion"] == "bloqueado"
    assert catalogo(client, client_h, situacion="bloqueado")["total"] == 1
    assert "mantenimiento" not in str(item(client, client_h, e["id"]))

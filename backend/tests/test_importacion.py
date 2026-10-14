import csv
import io
import uuid
from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.models.equipo import Equipo
from app.services import equipos_import

HEADER = [
    "codigo",
    "categoria",
    "nombre",
    "marca",
    "modelo",
    "numero_serie",
    "anio",
    "horometro",
    "patio",
    "tarifa_hora",
    "tarifa_dia",
    "requiere_lowboy",
    "requiere_operador_certificado",
    "notas",
    "spec_peso_kg",
    "spec_motor",
    "spec_combustible",
    "spec_oruga",
]


def fila(n: int = 1, **overrides: str) -> dict[str, str]:
    row = {
        "codigo": f"IMP-{n:03d}",
        "categoria": "Pavimentadora",
        "nombre": f"Pavimentadora importada {n}",
        "marca": "Vögele",
        "modelo": "MT 3000-2",
        "numero_serie": f"IMP-SN-{n:04d}",
        "anio": "2022",
        "horometro": "1500.5",
        "patio": "Patio Toluca CHRISCO",
        "tarifa_hora": "3400",
        "tarifa_dia": "",
        "requiere_lowboy": "si",
        "requiere_operador_certificado": "no",
        "notas": "",
        "spec_peso_kg": "18000",
        "spec_motor": "Cummins",
        "spec_combustible": "diésel",
        "spec_oruga": "sí",
    }
    return {**row, **overrides}


def a_csv(rows, header=HEADER, delimiter=",", encoding="utf-8-sig") -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=header, delimiter=delimiter, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode(encoding)


def importar(client, headers, data: bytes, dry_run: bool | None = None):
    url = "/admin/equipos/importar" + (
        "" if dry_run is None else f"?dry_run={str(dry_run).lower()}"
    )
    return client.post(url, files={"archivo": ("equipos.csv", data, "text/csv")}, headers=headers)


def total(client, headers) -> int:
    return client.get("/admin/equipos", headers=headers).json()["total"]


def test_por_defecto_solo_valida_y_no_guarda(client, admin_h, categoria) -> None:
    res = importar(client, admin_h, a_csv([fila(1), fila(2)]))
    assert res.status_code == 200
    assert res.json() == {"dry_run": True, "rows": 2, "created": 0, "errors": []}
    assert total(client, admin_h) == 0


def test_importar_crea_los_equipos_con_sus_datos(client, admin_h, categoria) -> None:
    res = importar(
        client,
        admin_h,
        a_csv([fila(1), fila(2, tarifa_hora="", tarifa_dia="25000")]),
        dry_run=False,
    )
    assert res.json() == {"dry_run": False, "rows": 2, "created": 2, "errors": []}
    items = client.get("/admin/equipos", headers=admin_h).json()["items"]
    primero = items[0]
    assert primero["codigo"] == "IMP-001" and primero["categoria_nombre"] == "Pavimentadora"
    assert primero["requiere_lowboy"] is True and primero["requiere_operador_certificado"] is False
    assert primero["horometro"] == 1500.5 and primero["anio"] == 2022
    assert primero["specs"] == {
        "peso_kg": 18000,
        "motor": "Cummins",
        "combustible": "Diésel",
        "oruga": True,
    }
    assert items[1]["tarifa_hora"] is None and items[1]["tarifa_dia"] == 25000


def test_lo_que_excel_guarda_como_punto_y_coma_y_ansi(client, admin_h, categoria) -> None:
    data = a_csv([fila(1, nombre="Pavimentadora ñandú")], delimiter=";", encoding="cp1252")
    res = importar(client, admin_h, data, dry_run=False)
    assert res.json()["created"] == 1, res.text
    assert client.get("/admin/equipos?q=ñandú", headers=admin_h).json()["total"] == 1


def test_los_errores_se_reportan_por_fila_y_no_se_guarda_nada(client, admin_h, categoria) -> None:
    filas = [
        fila(1),
        fila(2, categoria="Submarino"),
        fila(3, tarifa_hora="", tarifa_dia=""),
        fila(4, anio="mil"),
        fila(5, requiere_lowboy="quizá"),
        fila(6, spec_combustible="agua"),
        fila(7, spec_peso_kg="pesado"),
        fila(8, spec_peso_kg=""),
        fila(9, codigo="mal codigo"),
    ]
    res = importar(client, admin_h, a_csv(filas), dry_run=False).json()
    assert res["created"] == 0 and res["rows"] == 9
    por_fila = {e["row"]: e["message"] for e in res["errors"]}
    assert sorted(por_fila) == list(range(3, 11))  # la fila 2 (el primer equipo) es válida
    assert total(client, admin_h) == 0


def test_mensajes_claros_para_cada_error(client, admin_h, categoria) -> None:
    casos = {
        "categoria": (fila(1, categoria="Submarino"), "«Submarino» no existe"),
        "tarifa": (fila(1, tarifa_hora="", tarifa_dia=""), "tarifa por hora, por día o ambas"),
        "anio": (fila(1, anio="mil"), "anio: debe ser un número entero"),
        "booleano": (fila(1, requiere_lowboy="quizá"), "requiere_lowboy: debe ser sí o no"),
        "opcion": (fila(1, spec_combustible="agua"), "«Combustible» debe ser una de"),
        "numero": (fila(1, spec_peso_kg="pesado"), "spec_peso_kg: debe ser un número"),
        "obligatoria": (fila(1, spec_peso_kg=""), "«Peso» es obligatorio"),
        "codigo": (fila(1, codigo="mal codigo"), "código"),
        "tarifa negativa": (fila(1, tarifa_hora="-5"), "tarifa_hora: no puede ser negativo"),
        "tarifa cero": (fila(1, tarifa_hora="0"), "tarifa_hora: debe ser mayor que 0"),
        "vacio": (fila(1, nombre=""), "nombre"),
    }
    for nombre, (row, fragmento) in casos.items():
        res = importar(client, admin_h, a_csv([row])).json()
        assert res["errors"], nombre
        assert res["errors"][0]["row"] == 2 and fragmento in res["errors"][0]["message"], (
            nombre,
            res,
        )


def test_la_fila_uno_es_el_encabezado_y_los_datos_empiezan_en_la_dos(
    client, admin_h, categoria
) -> None:
    res = importar(client, admin_h, a_csv([fila(1), fila(2, categoria="Nada")])).json()
    assert [e["row"] for e in res["errors"]] == [3]


def test_duplicados_dentro_del_archivo_y_contra_la_base(
    client, admin_h, categoria, make_equipo
) -> None:
    make_equipo()  # EQ-001 / SN-0001
    filas = [
        fila(1),
        fila(2, codigo="imp-001"),
        fila(3, numero_serie="IMP-SN-0001"),
        fila(4, codigo="EQ-001"),
        fila(5, numero_serie="SN-0001"),
    ]
    res = importar(client, admin_h, a_csv(filas)).json()
    por_fila = {e["row"]: e["message"] for e in res["errors"]}
    assert 2 not in por_fila  # la primera aparición es válida
    assert "repetido" in por_fila[3] and "repetido" in por_fila[4]
    assert "ya existe" in por_fila[5] and "ya existe" in por_fila[6]


def test_columnas_faltantes_desconocidas_o_repetidas(client, admin_h, categoria) -> None:
    sin_nombre = [h for h in HEADER if h != "nombre"]
    res = importar(client, admin_h, a_csv([fila()], header=sin_nombre)).json()
    assert res["errors"] == [{"row": 1, "message": "Falta la columna «nombre»"}]

    res = importar(client, admin_h, a_csv([fila()], header=[*HEADER, "color"])).json()
    assert "Columna desconocida «color»" in res["errors"][0]["message"]

    res = importar(client, admin_h, a_csv([fila()], header=[*HEADER, "codigo"])).json()
    assert any("repetida" in e["message"] for e in res["errors"])


def test_especificacion_de_otra_categoria(client, admin_h, categoria) -> None:
    client.post("/admin/categorias", json={"nombre": "Grúa", "spec_fields": []}, headers=admin_h)
    res = importar(client, admin_h, a_csv([fila(1, categoria="grúa")])).json()
    assert "no tiene esa especificación" in res["errors"][0]["message"]


def test_archivo_vacio_o_ilegible(client, admin_h, categoria) -> None:
    assert importar(client, admin_h, b"").status_code == 422
    assert importar(
        client, admin_h, b"\xff\xfe\x00\x00 no es csv \x81\x8d\x8f\x90"
    ).status_code in (200, 422)


def test_limite_de_filas(client, admin_h, categoria) -> None:
    res = importar(client, admin_h, a_csv([fila(n) for n in range(1, 1002)]))
    assert res.status_code == 422 and "1000" in res.json()["detail"]


def test_filas_vacias_se_ignoran(client, admin_h, categoria) -> None:
    data = a_csv([fila(1), {}, fila(2)])
    assert importar(client, admin_h, data, dry_run=False).json()["created"] == 2


def test_una_carrera_con_el_mismo_codigo_no_deja_nada_a_medias(
    client, admin_h, categoria, monkeypatch
) -> None:
    """Otro usuario crea IMP-002 entre la validación y el guardado: no se guarda nada a medias."""
    original = equipos_import.equipos.commit

    def con_choque(session) -> None:  # noqa: ANN001
        with SessionLocal() as otra:
            otra.add(
                Equipo(
                    codigo="IMP-002",
                    categoria_id=uuid.UUID(categoria["id"]),
                    nombre="Intruso",
                    marca="x",
                    modelo="x",
                    numero_serie="INTRUSO",
                    patio="x",
                    tarifa_hora=Decimal(1),
                )
            )
            otra.commit()
        original(session)

    monkeypatch.setattr(equipos_import.equipos, "commit", con_choque)
    res = importar(client, admin_h, a_csv([fila(1), fila(2)]), dry_run=False)
    assert res.status_code == 409
    codigos = [e["codigo"] for e in client.get("/admin/equipos", headers=admin_h).json()["items"]]
    assert codigos == ["IMP-002"]  # solo el del intruso; IMP-001 no quedó guardado


def test_plantilla_con_y_sin_categoria(client, admin_h, ventas_h, categoria) -> None:
    res = client.get("/admin/equipos/importar/plantilla", headers=ventas_h)
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    cabecera = res.content.decode("utf-8-sig").splitlines()[0].split(",")
    assert cabecera[:3] == ["codigo", "categoria", "nombre"] and not any(
        c.startswith("spec_") for c in cabecera
    )

    res = client.get(
        f"/admin/equipos/importar/plantilla?categoria_id={categoria['id']}", headers=admin_h
    )
    cabecera = res.content.decode("utf-8-sig").splitlines()[0].split(",")
    assert [c for c in cabecera if c.startswith("spec_")] == [
        "spec_peso_kg",
        "spec_motor",
        "spec_combustible",
        "spec_oruga",
    ]
    assert res.content.startswith(b"\xef\xbb\xbf")  # BOM para Excel


def test_la_plantilla_descargada_se_puede_importar(client, admin_h, categoria) -> None:
    res = client.get(
        f"/admin/equipos/importar/plantilla?categoria_id={categoria['id']}", headers=admin_h
    )
    resultado = importar(client, admin_h, res.content).json()
    # La fila de ejemplo trae el peso vacío (obligatorio aquí): el aviso es útil, no un fallo.
    assert resultado["errors"] and "«Peso» es obligatorio" in resultado["errors"][0]["message"]


def test_solo_el_admin_importa(client, ventas_h, client_h, categoria) -> None:
    data = a_csv([fila(1)])
    assert importar(client, ventas_h, data).status_code == 403
    assert importar(client, client_h, data).status_code == 403
    assert (
        client.post(
            "/admin/equipos/importar", files={"archivo": ("a.csv", data, "text/csv")}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("valor", ["sí", "SI", "Si", "true", "1", "x", "Verdadero"])
def test_formas_de_decir_si(client, admin_h, categoria, valor) -> None:
    res = importar(client, admin_h, a_csv([fila(1, requiere_lowboy=valor)]), dry_run=False)
    assert res.json()["created"] == 1
    assert (
        client.get("/admin/equipos", headers=admin_h).json()["items"][0]["requiere_lowboy"] is True
    )

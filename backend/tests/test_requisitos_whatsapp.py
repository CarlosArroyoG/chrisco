"""Reglas puras de requisitos y mensaje de WhatsApp (no tocan la base de datos)."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.models.categoria import Categoria
from app.models.equipo import Equipo
from app.models.renta import OperadorModo, Renta, Transporte
from app.services import requisitos, whatsapp


def equipo(lowboy: bool = False, certificado: bool = False) -> Equipo:
    return Equipo(
        requiere_lowboy=lowboy,
        requiere_operador_certificado=certificado,
        categoria=Categoria(nombre="Pavimentadora"),
    )


def codes(items) -> list[str]:
    return [i.codigo for i in items]


BASE = ["contrato", "poliza", "anticipo"]


def test_siempre_se_piden_contrato_poliza_y_anticipo() -> None:
    for modo in OperadorModo:
        for transporte in Transporte:
            assert codes(requisitos.compute(equipo(), modo, transporte))[:3] == BASE


@pytest.mark.parametrize(
    ("lowboy", "certificado", "operador", "transporte", "esperado"),
    [
        # Operador de CHRISCO: sin licencia que presentar.
        (False, False, OperadorModo.CHRISCO, Transporte.RECOGE, [*BASE, "operador_chrisco"]),
        (
            False,
            False,
            OperadorModo.CHRISCO,
            Transporte.ENTREGA,
            [*BASE, "operador_chrisco", "flete"],
        ),
        # Operador propio: licencia federal; y certificado si el equipo lo exige.
        (False, False, OperadorModo.CLIENTE, Transporte.RECOGE, [*BASE, "licencia_federal"]),
        (
            False,
            True,
            OperadorModo.CLIENTE,
            Transporte.RECOGE,
            [*BASE, "licencia_federal", "operador_certificado"],
        ),
        # El certificado solo se pide cuando opera alguien ajeno a CHRISCO.
        (False, True, OperadorModo.CHRISCO, Transporte.RECOGE, [*BASE, "operador_chrisco"]),
        # Equipos que viajan en lowboy.
        (
            True,
            False,
            OperadorModo.CHRISCO,
            Transporte.ENTREGA,
            [*BASE, "operador_chrisco", "flete_lowboy"],
        ),
        (
            True,
            False,
            OperadorModo.CHRISCO,
            Transporte.RECOGE,
            [*BASE, "operador_chrisco", "lowboy_propio"],
        ),
        (
            True,
            True,
            OperadorModo.CLIENTE,
            Transporte.RECOGE,
            [*BASE, "licencia_federal", "operador_certificado", "lowboy_propio"],
        ),
    ],
)
def test_requisitos_segun_equipo_y_modalidad(
    lowboy, certificado, operador, transporte, esperado
) -> None:
    assert codes(requisitos.compute(equipo(lowboy, certificado), operador, transporte)) == esperado


def test_cargos_y_condiciones_se_distinguen_de_los_documentos() -> None:
    items = {
        i.codigo: i
        for i in requisitos.compute(equipo(lowboy=True), OperadorModo.CHRISCO, Transporte.ENTREGA)
    }
    assert items["contrato"].tipo == "documento" and items["contrato"].obligatorio
    assert items["anticipo"].tipo == "condicion"
    assert items["flete_lowboy"].tipo == "cargo" and not items["flete_lowboy"].obligatorio
    assert items["operador_chrisco"].tipo == "cargo" and not items["operador_chrisco"].obligatorio
    propio = {
        i.codigo: i
        for i in requisitos.compute(equipo(lowboy=True), OperadorModo.CLIENTE, Transporte.RECOGE)
    }
    assert propio["lowboy_propio"].tipo == "condicion" and propio["lowboy_propio"].obligatorio


def test_el_certificado_menciona_la_categoria() -> None:
    items = requisitos.compute(equipo(certificado=True), OperadorModo.CLIENTE, Transporte.RECOGE)
    certificado = next(i for i in items if i.codigo == "operador_certificado")
    assert "pavimentadora" in certificado.detalle


# ---------------------------------------------------------------- WhatsApp


def renta(**extra) -> Renta:
    base = dict(
        folio="CHR-2030-00007",
        desde=datetime(2030, 5, 1, 15, 0, tzinfo=UTC),  # 09:00 en la Ciudad de México
        hasta=datetime(2030, 5, 3, 23, 30, tzinfo=UTC),
        destino="Autopista Morelia - Guadalajara km 45",
        operador_modo=OperadorModo.CLIENTE,
        transporte=Transporte.ENTREGA,
        notas=None,
        requisitos=[
            i.model_dump()
            for i in requisitos.compute(
                equipo(lowboy=True), OperadorModo.CLIENTE, Transporte.ENTREGA
            )
        ],
        equipo=SimpleNamespace(
            nombre="Pavimentadora MT 3000", codigo="EQ-001", marca="Vögele", modelo="MT 3000-2"
        ),
        empresa=SimpleNamespace(razon_social="ICA Infraestructura SA de CV", rfc="ICA010101AB1"),
        solicitante=SimpleNamespace(full_name="Ana Torres"),
    )
    return SimpleNamespace(**{**base, **extra})  # type: ignore[return-value]


def test_el_mensaje_lleva_todo_lo_que_ventas_necesita() -> None:
    msg = whatsapp.build_message(renta())
    for texto in (
        "Ana Torres de ICA Infraestructura SA de CV (RFC ICA010101AB1)",
        "Pavimentadora MT 3000 (EQ-001) – Vögele MT 3000-2",
        "Del 01/05/2030 09:00 al 03/05/2030 17:30",  # en hora de México, no en UTC
        "Lugar de trabajo: Autopista Morelia - Guadalajara km 45",
        "Operador: Operador de mi empresa",
        "Traslado: Entrega CHRISCO en mi obra",
        "- Contrato de renta firmado",
        "- Licencia federal vigente del operador",
        "- Flete en lowboy a tu obra",
        "Folio CHR-2030-00007",
    ):
        assert texto in msg, texto
    assert "Notas" not in msg


def test_las_notas_aparecen_solo_si_las_hay() -> None:
    assert "• Notas: Entrar por el portón sur" in whatsapp.build_message(
        renta(notas="Entrar por el portón sur")
    )


def test_el_enlace_codifica_el_mensaje() -> None:
    url = whatsapp.build_url("Hola ñandú\nsegunda línea & más", "5217221234567")
    assert (
        url
        == "https://wa.me/5217221234567?text=Hola%20%C3%B1and%C3%BA%0Asegunda%20l%C3%ADnea%20%26%20m%C3%A1s"
    )


@pytest.mark.parametrize("numero", ["", "123", "+52 722 123 4567", "abc1234567890", "1" * 16])
def test_sin_numero_valido_no_hay_enlace(numero) -> None:
    assert whatsapp.build_url("hola", numero) is None


def test_usa_el_numero_configurado(monkeypatch) -> None:
    assert whatsapp.build_url("hola") is None  # por defecto no hay número
    monkeypatch.setattr(get_settings(), "sales_whatsapp_number", "5217221234567")
    assert whatsapp.build_url("hola") == "https://wa.me/5217221234567?text=hola"

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.schemas.equipo import CategoriaIn, SpecField
from app.services.specs import display_specs, validate_specs

FIELDS = [
    SpecField(key="peso_kg", label="Peso", type="number", unit="kg", required=True),
    SpecField(key="motor", label="Motor", type="text"),
    SpecField(
        key="combustible", label="Combustible", type="select", options=["Diésel", "Gasolina"]
    ),
    SpecField(key="oruga", label="Con orugas", type="boolean"),
]


def test_valores_validos_se_conservan() -> None:
    specs = {"peso_kg": 18000, "motor": "  Cummins  ", "combustible": "Diésel", "oruga": False}
    assert validate_specs(FIELDS, specs) == {
        "peso_kg": 18000,
        "motor": "Cummins",
        "combustible": "Diésel",
        "oruga": False,
    }


def test_los_opcionales_pueden_faltar_o_venir_vacios() -> None:
    assert validate_specs(FIELDS, {"peso_kg": 1, "motor": "", "oruga": None}) == {"peso_kg": 1}


@pytest.mark.parametrize(
    ("specs", "fragment"),
    [
        ({}, "«Peso» es obligatorio"),
        ({"peso_kg": "pesado"}, "«Peso» debe ser un número"),
        ({"peso_kg": True}, "«Peso» debe ser un número"),
        ({"peso_kg": float("inf")}, "«Peso» debe ser un número"),
        ({"peso_kg": 1, "motor": 5}, "«Motor» debe ser un texto"),
        ({"peso_kg": 1, "motor": "x" * 201}, "admite hasta 200"),
        ({"peso_kg": 1, "oruga": "si"}, "«Con orugas» debe ser sí o no"),
        ({"peso_kg": 1, "combustible": "Agua"}, "«Combustible» debe ser una de: Diésel, Gasolina"),
        ({"peso_kg": 1, "color": "rojo"}, "no tiene la especificación «color»"),
    ],
)
def test_valores_invalidos(specs, fragment) -> None:
    with pytest.raises(InvalidInput, match=fragment):
        validate_specs(FIELDS, specs)


def test_display_sigue_el_orden_de_la_categoria_y_formatea() -> None:
    shown = display_specs(
        FIELDS, {"oruga": True, "peso_kg": 18000.0, "motor": "Cummins", "viejo": "ignorado"}
    )
    assert [(s.label, s.value, s.unit) for s in shown] == [
        ("Peso", "18000", "kg"),
        ("Motor", "Cummins", None),
        ("Con orugas", "Sí", None),
    ]


@pytest.mark.parametrize(
    "field",
    [
        {"key": "Peso", "label": "x", "type": "number"},  # clave con mayúscula
        {"key": "1peso", "label": "x", "type": "number"},  # empieza con número
        {"key": "a", "label": "x", "type": "select", "options": ["solo una"]},
        {"key": "a", "label": "x", "type": "select", "options": ["A", "A"]},
        {"key": "a", "label": "x", "type": "text", "options": ["A", "B"]},
        {"key": "a", "label": "x", "type": "color"},
    ],
)
def test_definiciones_de_campo_invalidas(field) -> None:
    with pytest.raises(ValidationError):
        SpecField.model_validate(field)


def test_categoria_no_admite_claves_repetidas() -> None:
    dup = {"key": "peso", "label": "Peso", "type": "number"}
    with pytest.raises(ValidationError, match="repetir"):
        CategoriaIn(nombre="Grúa", spec_fields=[dup, dup])

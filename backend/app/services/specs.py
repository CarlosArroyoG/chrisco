"""Especificaciones flexibles: cada categoría define sus campos y cada equipo guarda sus valores."""

import math
from typing import Any

from app.core.errors import InvalidInput
from app.schemas.equipo import SpecField, SpecFieldType, SpecValueOut

_MAX_TEXT = 200


def parse_fields(raw: list[dict[str, Any]]) -> list[SpecField]:
    return [SpecField.model_validate(f) for f in raw]


def _clean(field: SpecField, value: Any) -> Any:
    name = f"«{field.label}»"
    match field.type:
        case SpecFieldType.TEXT:
            if not isinstance(value, str) or not value.strip():
                raise InvalidInput(f"{name} debe ser un texto")
            if len(value.strip()) > _MAX_TEXT:
                raise InvalidInput(f"{name} admite hasta {_MAX_TEXT} caracteres")
            return value.strip()
        case SpecFieldType.NUMBER:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise InvalidInput(f"{name} debe ser un número")
            if isinstance(value, float) and not math.isfinite(value):
                raise InvalidInput(f"{name} debe ser un número")
            return value
        case SpecFieldType.BOOLEAN:
            if not isinstance(value, bool):
                raise InvalidInput(f"{name} debe ser sí o no")
            return value
        case SpecFieldType.SELECT:
            if value not in field.options:
                raise InvalidInput(f"{name} debe ser una de: {', '.join(field.options)}")
            return value


def validate_specs(fields: list[SpecField], specs: dict[str, Any]) -> dict[str, Any]:
    """Valida los valores contra las definiciones de la categoría y devuelve los valores limpios."""
    by_key = {f.key: f for f in fields}
    unknown = sorted(set(specs) - set(by_key))
    if unknown:
        raise InvalidInput(f"La categoría no tiene la especificación «{unknown[0]}»")

    cleaned: dict[str, Any] = {}
    for field in fields:
        value = specs.get(field.key)
        if value is None or value == "":
            if field.required:
                raise InvalidInput(f"«{field.label}» es obligatorio")
            continue
        cleaned[field.key] = _clean(field, value)
    return cleaned


def _format(field: SpecField, value: Any) -> str:
    if field.type == SpecFieldType.BOOLEAN:
        return "Sí" if value else "No"
    if field.type == SpecFieldType.NUMBER:
        return f"{value:g}"
    return str(value)


def display_specs(fields: list[SpecField], specs: dict[str, Any]) -> list[SpecValueOut]:
    """Valores listos para mostrar, en el orden de la categoría. Ignora claves ya no definidas."""
    return [
        SpecValueOut(label=f.label, value=_format(f, specs[f.key]), unit=f.unit)
        for f in fields
        if f.key in specs
    ]

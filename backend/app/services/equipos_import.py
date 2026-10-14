"""Carga masiva de equipos desde CSV (el formato que exporta Excel). Es todo o nada."""

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import InvalidInput
from app.models.categoria import Categoria
from app.models.equipo import Equipo
from app.schemas.equipo import EquipoIn, ImportResult, RowError, SpecField, SpecFieldType
from app.services import categorias, equipos, specs

MAX_ROWS = 1000
SPEC_PREFIX = "spec_"
REQUIRED = ["codigo", "categoria", "nombre", "marca", "modelo", "numero_serie"]
OPTIONAL = [
    "anio",
    "horometro",
    "patio",
    "tarifa_hora",
    "tarifa_dia",
    "requiere_lowboy",
    "requiere_operador_certificado",
    "notas",
]
_TRUE = {"si", "sí", "true", "1", "x", "yes", "verdadero"}
_FALSE = {"no", "false", "0", "", "falso"}

_PYDANTIC_TEXT = {
    "missing": "es obligatorio",
    "string_too_short": "es demasiado corto",
    "string_too_long": "es demasiado largo",
    "int_parsing": "debe ser un número entero",
    "decimal_parsing": "debe ser un número",
    "decimal_type": "debe ser un número",
    "greater_than": "debe ser mayor que 0",
    "greater_than_equal": "no puede ser negativo",
    "less_than_equal": "es demasiado grande",
    "decimal_max_digits": "tiene demasiados dígitos",
    "decimal_max_places": "tiene demasiados decimales",
}


def template_csv(categoria: Categoria | None = None) -> str:
    """Encabezados de ejemplo; con una categoría, añade sus columnas de especificaciones."""
    columns = REQUIRED + OPTIONAL
    example = [
        "EQ-001",
        categoria.nombre if categoria else "Pavimentadora",
        "Pavimentadora MT 3000",
        "Vögele",
        "MT 3000-2",
        "SN-0001",
        "2021",
        "2400.5",
        "Patio Toluca CHRISCO",
        "3400",
        "",
        "si",
        "si",
        "",
    ]
    if categoria:
        fields = specs.parse_fields(categoria.spec_fields)
        columns += [SPEC_PREFIX + f.key for f in fields]
        example += ["" for _ in fields]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(columns)
    writer.writerow(example)
    return "﻿" + out.getvalue()  # BOM: Excel abre bien las tildes


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise InvalidInput("No se pudo leer el archivo: guárdalo como CSV (UTF-8)")


def _bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ValueError("debe ser sí o no")


def _spec_value(field: SpecField, raw: str) -> Any:
    raw = raw.strip()
    match field.type:
        case SpecFieldType.NUMBER:
            try:
                number = Decimal(raw.replace("$", "").replace(" ", ""))
            except InvalidOperation:
                raise ValueError("debe ser un número") from None
            return int(number) if number == number.to_integral_value() else float(number)
        case SpecFieldType.BOOLEAN:
            return _bool(raw)
        case SpecFieldType.SELECT:
            by_lower = {o.lower(): o for o in field.options}
            return by_lower.get(raw.lower(), raw)
        case _:
            return raw


def _pydantic_message(error: Any) -> str:
    field = str(error["loc"][-1]) if error["loc"] else ""
    if error["type"] == "value_error":
        text = str(error["msg"]).removeprefix("Value error, ")
    else:
        text = _PYDANTIC_TEXT.get(error["type"], "no es válido")
    return f"{field}: {text}" if field and field != "__root__" else text


def _build_row(
    row: dict[str, str], categories: dict[str, Categoria], spec_columns: set[str]
) -> EquipoIn:
    """Convierte una fila del CSV en un `EquipoIn`; lanza ValueError con un mensaje claro."""
    categoria = categories.get(row["categoria"].strip().lower())
    if categoria is None:
        raise ValueError(f"categoria: «{row['categoria'].strip()}» no existe")

    fields = {f.key: f for f in specs.parse_fields(categoria.spec_fields)}
    spec_values: dict[str, Any] = {}
    for column in spec_columns:
        key = column.removeprefix(SPEC_PREFIX)
        raw = row.get(column, "").strip()
        if not raw:
            continue
        if key not in fields:
            raise ValueError(
                f"{column}: la categoría «{categoria.nombre}» no tiene esa especificación"
            )
        try:
            spec_values[key] = _spec_value(fields[key], raw)
        except ValueError as exc:
            raise ValueError(f"{column}: {exc}") from None

    payload: dict[str, Any] = {
        name: value.strip()
        for name, value in row.items()
        if name in REQUIRED + OPTIONAL and name != "categoria"
    }
    for flag in ("requiere_lowboy", "requiere_operador_certificado"):
        try:
            payload[flag] = _bool(row.get(flag, ""))
        except ValueError as exc:
            raise ValueError(f"{flag}: {exc}") from None
    for name in ("anio", "horometro", "patio", "tarifa_hora", "tarifa_dia", "notas"):
        if not payload.get(name):
            payload.pop(name, None)  # vacío = usar el valor por defecto o ninguno
    payload["categoria_id"] = categoria.id
    payload["specs"] = spec_values

    try:
        data = EquipoIn.model_validate(payload)
        data.specs = specs.validate_specs(list(fields.values()), data.specs)
    except ValidationError as exc:
        raise ValueError("; ".join(_pydantic_message(e) for e in exc.errors())) from None
    except InvalidInput as exc:
        raise ValueError(exc.detail) from None
    return data


def import_csv(db: Session, raw: bytes, *, dry_run: bool) -> ImportResult:
    text = _decode(raw)
    rows = list(csv.reader(io.StringIO(text), delimiter=_delimiter(text)))
    if not rows:
        raise InvalidInput("El archivo está vacío")
    header = [h.strip().lower() for h in rows[0]]
    body = [r for r in rows[1:] if any(cell.strip() for cell in r)]
    if len(body) > MAX_ROWS:
        raise InvalidInput(f"El archivo admite hasta {MAX_ROWS} equipos por carga")

    known = set(REQUIRED + OPTIONAL)
    spec_columns = {h for h in header if h.startswith(SPEC_PREFIX)}
    structure = [
        *(f"Falta la columna «{c}»" for c in REQUIRED if c not in header),
        *(f"Columna desconocida «{h}»" for h in header if h not in known | spec_columns),
        *(f"La columna «{h}» está repetida" for h in set(header) if header.count(h) > 1),
    ]
    if structure:
        return ImportResult(
            dry_run=dry_run,
            rows=len(body),
            created=0,
            errors=[RowError(row=1, message=m) for m in structure],
        )

    categories = {c.nombre.lower(): c for c in categorias.list_categorias(db)}
    taken_codes = set(db.scalars(select(Equipo.codigo)))
    taken_serials = set(db.scalars(select(Equipo.numero_serie)))
    errors: list[RowError] = []
    valid: list[EquipoIn] = []
    for number, cells in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in cells):
            continue
        row = dict(zip(header, cells, strict=False))
        try:
            data = _build_row(row, categories, spec_columns)
            for value, seen, label in (
                (data.codigo, taken_codes, "código"),
                (data.numero_serie, taken_serials, "número de serie"),
            ):
                if value in seen:
                    raise ValueError(
                        f"el {label} «{value}» ya existe o está repetido en el archivo"
                    )
                seen.add(value)
        except ValueError as exc:
            errors.append(RowError(row=number, message=str(exc)))
            continue
        valid.append(data)

    if errors or dry_run:
        return ImportResult(dry_run=dry_run, rows=len(body), created=0, errors=errors)

    for data in valid:
        equipo = Equipo()
        equipos.apply_data(db, equipo, data)
        db.add(equipo)
    equipos.commit(db)
    return ImportResult(dry_run=False, rows=len(body), created=len(valid), errors=[])


def _delimiter(text: str) -> str:
    first = text.splitlines()[0] if text.strip() else ""
    return max((",", ";", "\t"), key=first.count)

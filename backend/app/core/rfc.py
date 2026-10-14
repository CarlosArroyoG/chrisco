import re

# 3 letras (persona moral) o 4 (física) + fecha AAMMDD + homoclave de 3 caracteres.
_RFC_RE = re.compile(r"^[A-ZÑ&]{3,4}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[A-Z0-9]{3}$")
# RFC genéricos del SAT (público en general / extranjeros): no identifican a una empresa.
_GENERIC_RFCS = {"XAXX010101000", "XEXX010101000"}


def normalize_rfc(value: str) -> str:
    """Devuelve el RFC en mayúsculas y sin espacios, o lanza ValueError si no es válido."""
    rfc = re.sub(r"[\s-]", "", value).upper()
    if rfc in _GENERIC_RFCS or len(rfc) not in (12, 13) or not _RFC_RE.match(rfc):
        raise ValueError("El RFC no tiene un formato válido")
    return rfc

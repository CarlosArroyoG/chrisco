"""Mensaje de WhatsApp para el agente de ventas. No usa ninguna API: arma un enlace `wa.me`."""

import re
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.models.renta import OperadorModo, Renta, Transporte
from app.schemas.renta import Requisito

_NUMBER_RE = re.compile(r"^\d{10,15}$")
_OPERADOR = {
    OperadorModo.CHRISCO: "Operador de CHRISCO",
    OperadorModo.CLIENTE: "Operador de mi empresa",
}
_TRANSPORTE = {
    Transporte.ENTREGA: "Entrega CHRISCO en mi obra",
    Transporte.RECOGE: "Lo recojo en el patio",
}


def _local(moment: datetime) -> str:
    return moment.astimezone(ZoneInfo(get_settings().timezone)).strftime("%d/%m/%Y %H:%M")


def build_message(renta: Renta) -> str:
    equipo, empresa, usuario = renta.equipo, renta.empresa, renta.solicitante
    lines = [
        f"Hola, soy {usuario.full_name} de {empresa.razon_social} (RFC {empresa.rfc}).",
        "Quiero solicitar la renta de este equipo:",
        f"• {equipo.nombre} ({equipo.codigo}) – {equipo.marca} {equipo.modelo}",
        f"• Del {_local(renta.desde)} al {_local(renta.hasta)}",
        f"• Lugar de trabajo: {renta.destino}",
        f"• Operador: {_OPERADOR[renta.operador_modo]}",
        f"• Traslado: {_TRANSPORTE[renta.transporte]}",
    ]
    if renta.notas:
        lines.append(f"• Notas: {renta.notas}")
    lines.append("")
    lines.append("Según la plataforma necesito:")
    for item in (Requisito.model_validate(r) for r in renta.requisitos):
        lines.append(f"- {item.titulo}")
    lines.append("")
    lines.append(f"Folio {renta.folio}. El equipo quedó reservado unos minutos.")
    lines.append("Quedo atento a la cotización.")
    return "\n".join(lines)


def build_url(message: str, number: str | None = None) -> str | None:
    """Enlace para abrir WhatsApp con el mensaje escrito. None si no hay un número válido."""
    digits = number if number is not None else get_settings().sales_whatsapp_number
    if not _NUMBER_RE.match(digits):
        return None
    return f"https://wa.me/{digits}?text={quote(message)}"

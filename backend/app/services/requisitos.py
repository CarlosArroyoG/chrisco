"""Qué se le pide al cliente según el equipo y cómo quiere rentarlo. Reglas puras."""

from app.models.equipo import Equipo
from app.models.renta import OperadorModo, Transporte
from app.schemas.renta import Requisito


def compute(equipo: Equipo, operador_modo: OperadorModo, transporte: Transporte) -> list[Requisito]:
    """Requisitos, condiciones y cargos previstos. El orden es el que se muestra al cliente."""
    items: list[Requisito] = [
        Requisito(
            codigo="contrato",
            titulo="Contrato de renta firmado",
            detalle="Te lo enviamos junto con la cotización; se firma antes de la entrega.",
            tipo="documento",
        ),
        Requisito(
            codigo="poliza",
            titulo="Póliza de seguro vigente",
            detalle="Debe cubrir el equipo durante todo el periodo de la renta.",
            tipo="documento",
        ),
        Requisito(
            codigo="anticipo",
            titulo="Anticipo por transferencia",
            detalle="Se confirma con tu comprobante de pago. El monto va en la cotización.",
            tipo="condicion",
        ),
    ]

    if operador_modo == OperadorModo.CLIENTE:
        items.append(
            Requisito(
                codigo="licencia_federal",
                titulo="Licencia federal vigente del operador",
                detalle="Súbela con foto: verificamos su vigencia con el código QR de la licencia.",
                tipo="documento",
            )
        )
        if equipo.requiere_operador_certificado:
            items.append(
                Requisito(
                    codigo="operador_certificado",
                    titulo="Operador certificado",
                    detalle=f"Este equipo ({equipo.categoria.nombre.lower()}) solo lo opera "
                    "personal certificado: presenta su certificado.",
                    tipo="documento",
                )
            )
    else:
        items.append(
            Requisito(
                codigo="operador_chrisco",
                titulo="Operador de CHRISCO",
                detalle="Su jornada se cobra junto con la renta, según la cotización.",
                tipo="cargo",
                obligatorio=False,
            )
        )

    if equipo.requiere_lowboy:
        if transporte == Transporte.ENTREGA:
            items.append(
                Requisito(
                    codigo="flete_lowboy",
                    titulo="Flete en lowboy a tu obra",
                    detalle="Lo lleva y lo recoge CHRISCO. Se cotiza según la distancia e incluye "
                    "el tractocamión que jala el lowboy.",
                    tipo="cargo",
                    obligatorio=False,
                )
            )
        else:
            items.append(
                Requisito(
                    codigo="lowboy_propio",
                    titulo="Lowboy y tractocamión propios",
                    detalle="Este equipo no se mueve por su cuenta: debes llegar al patio con un "
                    "lowboy y un tractocamión con capacidad suficiente.",
                    tipo="condicion",
                )
            )
    elif transporte == Transporte.ENTREGA:
        items.append(
            Requisito(
                codigo="flete",
                titulo="Entrega en tu obra",
                detalle="El traslado se cotiza según la distancia.",
                tipo="cargo",
                obligatorio=False,
            )
        )
    return items

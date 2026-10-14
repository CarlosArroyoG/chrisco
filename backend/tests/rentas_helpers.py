"""Ayudantes compartidos por las pruebas de rentas, cotizaciones y pagos."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

NOW = datetime.now(UTC).replace(microsecond=0)


def h(hours: float) -> datetime:
    """Un instante a `hours` horas de ahora."""
    return NOW + timedelta(hours=hours)


def solicitud(equipo_id: str, a: float = 24, b: float = 32, **extra: Any) -> dict[str, Any]:
    return {
        "equipo_id": equipo_id,
        "desde": h(a).isoformat(),
        "hasta": h(b).isoformat(),
        "destino": "Autopista Morelia - Guadalajara km 45",
        "operador_modo": "chrisco",
        "transporte": "entrega",
        **extra,
    }


def pedir(
    client: Any, headers: dict[str, str], equipo_id: str, a: float = 24, b: float = 32, **extra: Any
):  # noqa: ANN201
    """Solicitud de renta de un cliente (POST /rentas/solicitudes)."""
    return client.post(
        "/rentas/solicitudes", json=solicitud(equipo_id, a, b, **extra), headers=headers
    )


def vencer(db: Session, renta_id: str) -> None:
    """Hace que la reserva de esa solicitud haya vencido hace un minuto."""
    db.execute(
        text(
            "UPDATE bloqueos SET vence_en = now() - interval '1 minute' "
            "WHERE id = (SELECT bloqueo_id FROM rentas WHERE id = :id)"
        ),
        {"id": renta_id},
    )
    db.commit()

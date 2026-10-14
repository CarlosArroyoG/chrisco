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


# Cotización de referencia: 8 × 3,400 + 4,500 = 31,700 → IVA 5,072 → total 36,772 → anticipo 11,031.60
PARTIDAS = [
    {
        "concepto": "renta",
        "descripcion": "Renta de Pavimentadora 1",
        "cantidad": 8,
        "unidad": "hora",
        "precio_unitario": 3400,
    },
    {
        "concepto": "flete",
        "descripcion": "Flete en lowboy a la obra",
        "cantidad": 1,
        "unidad": "servicio",
        "precio_unitario": 4500,
    },
]
TOTAL = 36772
ANTICIPO = 11031.6


def cotizar(
    client: Any, headers: dict[str, str], renta_id: str, partidas: Any = None, **extra: Any
):  # noqa: ANN201
    """Ventas cotiza una renta (POST /rentas/{id}/cotizacion)."""
    body = {"partidas": PARTIDAS if partidas is None else partidas, **extra}
    return client.post(f"/rentas/{renta_id}/cotizacion", json=body, headers=headers)


def apartar(
    client: Any, client_h: dict[str, str], staff_h: dict[str, str], equipo_id: str, **extra: Any
) -> dict[str, Any]:
    """Lleva una solicitud hasta `apartada`: solicitar, cotizar y aceptar. Devuelve la renta."""
    renta = pedir(client, client_h, equipo_id, **extra).json()
    assert cotizar(client, staff_h, renta["id"]).status_code == 201
    res = client.post(f"/rentas/{renta['id']}/cotizacion/aceptar", headers=client_h)
    assert res.status_code == 200, res.text
    return res.json()

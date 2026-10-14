"""Lo que debe cumplirse para confirmar una renta apartada: documentos, condiciones y anticipo."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Conflict, InvalidInput, NotFound
from app.models.cotizacion import Cotizacion, CotizacionEstado
from app.models.cumplimiento import Pago, RentaDocumento, RevisionEstado
from app.models.renta import Renta, RentaEstado
from app.models.user import User
from app.schemas.cumplimiento import (
    ChecklistItem,
    CumplimientoOut,
    DocumentoOut,
    PagoIn,
    PagoOut,
    Situacion,
)
from app.schemas.renta import Requisito
from app.services import disponibilidad
from app.services.storage import PrivateStorage

MAX_FILES_PER_REQUISITO = 10
MAX_PAYMENTS = 20
_PAYABLE = (
    RentaEstado.APARTADA,
    RentaEstado.CONFIRMADA,
    RentaEstado.EN_RENTA,
    RentaEstado.DEVUELTA,
)
ANTICIPO = "anticipo"


def accepted_quote(renta: Renta) -> Cotizacion | None:
    return next((c for c in renta.cotizaciones if c.estado == CotizacionEstado.ACEPTADA), None)


def _requisitos(renta: Renta) -> list[Requisito]:
    return [Requisito.model_validate(r) for r in renta.requisitos]


def paid(renta: Renta) -> Decimal:
    """Pagos ya confirmados por el personal."""
    return sum((p.monto for p in renta.pagos if p.estado == RevisionEstado.APROBADO), Decimal(0))


def _pending(renta: Renta) -> Decimal:
    return sum((p.monto for p in renta.pagos if p.estado == RevisionEstado.PENDIENTE), Decimal(0))


def _document_situation(renta: Renta, codigo: str) -> Situacion:
    docs = [d for d in renta.documentos if d.requisito == codigo]
    if any(d.estado == RevisionEstado.APROBADO for d in docs):
        return "cumplido"
    if any(d.estado == RevisionEstado.PENDIENTE for d in docs):
        return "en_revision"
    return "rechazado" if docs else "pendiente"


def _anticipo_situation(renta: Renta) -> Situacion:
    quote = accepted_quote(renta)
    required = quote.anticipo_monto if quote else Decimal(0)
    if paid(renta) >= required:
        return "cumplido"
    if paid(renta) + _pending(renta) >= required:
        return "en_revision"
    return (
        "rechazado"
        if any(p.estado == RevisionEstado.RECHAZADO for p in renta.pagos)
        else "pendiente"
    )


def checklist(renta: Renta) -> list[ChecklistItem]:
    """Documentos y condiciones con su situación. Los cargos no se listan: se cotizan."""
    items: list[ChecklistItem] = []
    for item in _requisitos(renta):
        if item.tipo == "cargo":
            continue
        if item.tipo == "documento":
            situation = _document_situation(renta, item.codigo)
        elif item.codigo == ANTICIPO:
            situation = _anticipo_situation(renta)
        else:
            situation = "cumplido" if item.codigo in renta.condiciones_verificadas else "pendiente"
        items.append(ChecklistItem(**item.model_dump(), situacion=situation))
    return items


def try_confirm(db: Session, renta: Renta) -> bool:
    """Si ya se cumplió todo lo obligatorio, la renta pasa a `confirmada` y el equipo queda firme.

    No hace commit: lo decide quien llama. Devuelve True si acaba de confirmarse.
    """
    if renta.estado != RentaEstado.APARTADA or renta.bloqueo is None:
        return False
    if any(i.obligatorio and i.situacion != "cumplido" for i in checklist(renta)):
        return False
    disponibilidad.confirm_rental(db, renta.bloqueo, commit=False)
    renta.estado = RentaEstado.CONFIRMADA
    return True


def _lock(db: Session, renta: Renta) -> None:
    """Serializa las revisiones de una misma renta y recarga su estado.

    Sin esto, dos personas que aprueban a la vez los dos últimos requisitos no se verían entre sí
    (cada transacción vería al otro como pendiente) y la renta nunca se confirmaría.
    """
    db.execute(select(Renta.id).where(Renta.id == renta.id).with_for_update())
    db.refresh(renta)


def _require_open(renta: Renta) -> None:
    if renta.estado != RentaEstado.APARTADA:
        raise Conflict("Solo se pueden entregar requisitos mientras la renta está apartada")


# ---------------------------------------------------------------------- documentos


def upload_document(
    db: Session,
    storage: PrivateStorage,
    renta: Renta,
    user: User,
    requisito: str,
    data: bytes,
    extension: str,
    filename: str,
) -> RentaDocumento:
    _require_open(renta)
    valid = {i.codigo for i in _requisitos(renta) if i.tipo == "documento"}
    if requisito not in valid:
        raise InvalidInput("Ese requisito no pide un documento")
    if sum(1 for d in renta.documentos if d.requisito == requisito) >= MAX_FILES_PER_REQUISITO:
        raise Conflict(f"Ya subiste {MAX_FILES_PER_REQUISITO} archivos para este requisito")
    key = storage.save(data, extension)
    documento = RentaDocumento(
        requisito=requisito, filename=filename[:200] or "documento", key=key, subido_por_id=user.id
    )
    renta.documentos.append(documento)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return documento


def find[T: (RentaDocumento, Pago)](items: list[T], item_id: uuid.UUID, label: str) -> T:
    found = next((i for i in items if i.id == item_id), None)
    if found is None:
        raise NotFound(f"{label} no encontrado")
    return found


def review_document(
    db: Session, renta: Renta, doc_id: uuid.UUID, staff: User, aprobado: bool, nota: str | None
) -> tuple[RentaDocumento, bool]:
    """Aprueba o rechaza un documento. Devuelve (documento, la renta quedó confirmada)."""
    _lock(db, renta)
    _require_open(renta)
    documento = find(renta.documentos, doc_id, "Documento")
    if documento.estado != RevisionEstado.PENDIENTE:
        raise Conflict("Este documento ya fue revisado")
    documento.estado = RevisionEstado.APROBADO if aprobado else RevisionEstado.RECHAZADO
    documento.nota_revision = nota
    documento.revisado_por_id = staff.id
    documento.revisado_at = datetime.now(UTC)
    confirmed = try_confirm(db, renta)
    db.commit()
    return documento, confirmed


# ---------------------------------------------------------------------- pagos


def report_payment(
    db: Session,
    storage: PrivateStorage,
    renta: Renta,
    user: User,
    data: PagoIn,
    comprobante: bytes,
    extension: str,
) -> Pago:
    if renta.estado not in _PAYABLE:
        raise Conflict("Todavía no se pueden reportar pagos de esta renta")
    quote = accepted_quote(renta)
    if quote is None:
        raise Conflict("Esta renta no tiene una cotización aceptada")
    if data.fecha_pago > datetime.now(ZoneInfo(get_settings().timezone)).date():
        raise InvalidInput("La fecha del pago no puede ser futura")
    if len(renta.pagos) >= MAX_PAYMENTS:
        raise Conflict("Esta renta ya tiene demasiados pagos registrados")
    if data.monto > quote.total - paid(renta):
        raise Conflict("El pago es mayor que el saldo pendiente de la renta")
    key = storage.save(comprobante, extension)
    pago = Pago(
        monto=data.monto,
        fecha_pago=data.fecha_pago,
        referencia=data.referencia,
        comprobante_key=key,
        reportado_por_id=user.id,
    )
    renta.pagos.append(pago)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return pago


def review_payment(
    db: Session, renta: Renta, pago_id: uuid.UUID, staff: User, confirmado: bool, nota: str | None
) -> tuple[Pago, bool]:
    """Confirma o rechaza un pago. Devuelve (pago, la renta quedó confirmada)."""
    _lock(db, renta)
    if renta.estado not in _PAYABLE:
        raise Conflict("Esta renta ya no admite revisar pagos")
    pago = find(renta.pagos, pago_id, "Pago")
    if pago.estado != RevisionEstado.PENDIENTE:
        raise Conflict("Este pago ya fue revisado")
    quote = accepted_quote(renta)
    if confirmado and quote is not None and pago.monto > quote.total - paid(renta):
        raise Conflict("Confirmar este pago rebasaría el total de la renta")
    pago.estado = RevisionEstado.APROBADO if confirmado else RevisionEstado.RECHAZADO
    pago.nota_revision = nota
    pago.revisado_por_id = staff.id
    pago.revisado_at = datetime.now(UTC)
    confirmed = try_confirm(db, renta)
    db.commit()
    return pago, confirmed


# ---------------------------------------------------------------------- condiciones


def set_condicion(db: Session, renta: Renta, codigo: str, cumplida: bool) -> bool:
    """Marca una condición (que no sea documento ni anticipo) como verificada o no.

    Devuelve True si con eso la renta quedó confirmada.
    """
    _lock(db, renta)
    _require_open(renta)
    valid = {i.codigo for i in _requisitos(renta) if i.tipo == "condicion" and i.codigo != ANTICIPO}
    if codigo not in valid:
        raise InvalidInput("Esa condición no se verifica a mano")
    current = [c for c in renta.condiciones_verificadas if c != codigo]
    renta.condiciones_verificadas = [*current, codigo] if cumplida else current
    confirmed = try_confirm(db, renta)
    db.commit()
    return confirmed


# ---------------------------------------------------------------------- salida


def document_out(documento: RentaDocumento) -> DocumentoOut:
    return DocumentoOut(
        id=documento.id,
        requisito=documento.requisito,
        filename=documento.filename,
        estado=documento.estado,
        nota_revision=documento.nota_revision,
        subido_por_nombre=documento.subido_por.full_name,
        created_at=documento.created_at,
        revisado_at=documento.revisado_at,
    )


def payment_out(pago: Pago) -> PagoOut:
    return PagoOut(
        id=pago.id,
        monto=pago.monto,
        fecha_pago=pago.fecha_pago,
        referencia=pago.referencia,
        estado=pago.estado,
        nota_revision=pago.nota_revision,
        reportado_por_nombre=pago.reportado_por.full_name,
        created_at=pago.created_at,
        revisado_at=pago.revisado_at,
    )


def to_out(renta: Renta) -> CumplimientoOut:
    quote = accepted_quote(renta)
    total = quote.total if quote else None
    cobrado = paid(renta)
    return CumplimientoOut(
        checklist=checklist(renta),
        documentos=[document_out(d) for d in renta.documentos],
        pagos=[payment_out(p) for p in renta.pagos],
        total=total,
        anticipo_requerido=quote.anticipo_monto if quote else None,
        pagado=cobrado,
        saldo=total - cobrado if total is not None else None,
        confirmada=renta.estado
        in (
            RentaEstado.CONFIRMADA,
            RentaEstado.EN_RENTA,
            RentaEstado.DEVUELTA,
            RentaEstado.CERRADA,
        ),
    )

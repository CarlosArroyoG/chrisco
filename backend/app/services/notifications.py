"""Textos de los correos del sistema. Una función por correo; devuelven un `Mail` listo."""

from app.core.config import get_settings
from app.core.security import create_token
from app.models.empresa import Empresa
from app.models.renta import Renta
from app.models.user import User
from app.schemas.mantenimiento import AtencionItem
from app.services.mailer import Mail


def _link(path: str, token: str) -> str:
    return f"{get_settings().frontend_url}/{path}?token={token}"


def _url(path: str) -> str:
    return f"{get_settings().frontend_url}{path}"


def verification_mail(user: User) -> Mail:
    token = create_token(user.id, user.token_version, "verify_email")
    return Mail(
        to=user.email,
        subject="Confirma tu correo en CHRISCO Go",
        body=(
            f"Hola {user.full_name},\n\n"
            "Confirma tu correo para activar tu cuenta:\n"
            f"{_link('verificar-correo', token)}\n\n"
            f"El enlace vence en {get_settings().verify_email_hours} horas."
        ),
    )


def invitation_mail(user: User, empresa: Empresa, invited_by: User) -> Mail:
    token = create_token(user.id, user.token_version, "invite")
    return Mail(
        to=user.email,
        subject=f"{invited_by.full_name} te invitó a CHRISCO Go",
        body=(
            f"Hola {user.full_name},\n\n"
            f"{invited_by.full_name} te dio acceso a CHRISCO Go por {empresa.razon_social}.\n"
            "Crea tu contraseña aquí:\n"
            f"{_link('aceptar-invitacion', token)}\n\n"
            f"El enlace vence en {get_settings().invite_days} días."
        ),
    )


def staff_invitation_mail(user: User, invited_by: User) -> Mail:
    token = create_token(user.id, user.token_version, "invite")
    return Mail(
        to=user.email,
        subject=f"{invited_by.full_name} te dio acceso al equipo de CHRISCO Go",
        body=(
            f"Hola {user.full_name},\n\n"
            f"{invited_by.full_name} te dio acceso a CHRISCO Go como {user.role.value}.\n"
            "Crea tu contraseña aquí:\n"
            f"{_link('aceptar-invitacion', token)}\n\n"
            f"El enlace vence en {get_settings().invite_days} días."
        ),
    )


def password_reset_mail(user: User) -> Mail:
    token = create_token(user.id, user.token_version, "reset_password")
    return Mail(
        to=user.email,
        subject="Recupera tu contraseña de CHRISCO Go",
        body=(
            f"Hola {user.full_name},\n\n"
            "Recibimos una solicitud para cambiar tu contraseña. Si fuiste tú, hazlo aquí:\n"
            f"{_link('recuperar-contrasena', token)}\n\n"
            f"El enlace vence en {get_settings().reset_password_minutes} minutos. "
            "Si no lo pediste, ignora este correo."
        ),
    )


def company_approved_mail(user: User, empresa: Empresa) -> Mail:
    return Mail(
        to=user.email,
        subject="Tu empresa fue aprobada en CHRISCO Go",
        body=(
            f"Hola {user.full_name},\n\n"
            f"{empresa.razon_social} ya está aprobada. Ya puedes solicitar maquinaria "
            f"y dar acceso a otros usuarios de tu empresa:\n{get_settings().frontend_url}"
        ),
    )


def company_rejected_mail(user: User, empresa: Empresa) -> Mail:
    return Mail(
        to=user.email,
        subject="Revisión de tu empresa en CHRISCO Go",
        body=(
            f"Hola {user.full_name},\n\n"
            f"No pudimos aprobar a {empresa.razon_social}.\n"
            f"Motivo: {empresa.motivo_rechazo}\n\n"
            f"Corrige tus datos y vuelve a enviarlos desde tu cuenta: {get_settings().frontend_url}"
        ),
    )


def quote_ready_mail(user: User, renta: Renta) -> Mail:
    return Mail(
        to=user.email,
        subject=f"Tu cotización {renta.folio} está lista",
        body=(
            f"Hola {user.full_name},\n\n"
            f"Ya tienes la cotización de {renta.equipo.nombre} ({renta.folio}). "
            "Revísala y acéptala para apartar el equipo:\n"
            f"{_url(f'/cliente/rentas/{renta.id}')}\n\n"
            "Al aceptar, el equipo queda apartado unas horas mientras cumples los requisitos."
        ),
    )


def quote_accepted_mail(staff: User, renta: Renta) -> Mail:
    return Mail(
        to=staff.email,
        subject=f"{renta.empresa.razon_social} aceptó la cotización {renta.folio}",
        body=(
            f"{renta.empresa.razon_social} aceptó la cotización de {renta.equipo.nombre}.\n"
            "El equipo quedó apartado; falta que cumpla los requisitos y pague el anticipo:\n"
            f"{_url(f'/admin/rentas/{renta.id}')}"
        ),
    )


def request_rejected_mail(user: User, renta: Renta) -> Mail:
    return Mail(
        to=user.email,
        subject=f"Sobre tu solicitud {renta.folio}",
        body=(
            f"Hola {user.full_name},\n\n"
            f"No pudimos atender tu solicitud de {renta.equipo.nombre} ({renta.folio}).\n"
            f"Motivo: {renta.motivo_cierre}\n\n"
            f"Puedes pedir otro equipo o fechas distintas: {_url('/cliente/catalogo')}"
        ),
    )


def document_rejected_mail(user: User, renta: Renta, requisito: str, nota: str | None) -> Mail:
    return Mail(
        to=user.email,
        subject=f"Revisa un documento de tu renta {renta.folio}",
        body=(
            f"Hola {user.full_name},\n\n"
            f"No pudimos aprobar «{requisito}» de tu renta {renta.folio}.\n"
            f"Motivo: {nota}\n\n"
            f"Súbelo de nuevo mientras el equipo siga apartado: "
            f"{_url(f'/cliente/rentas/{renta.id}')}"
        ),
    )


def payment_reviewed_mail(user: User, renta: Renta, confirmado: bool, nota: str | None) -> Mail:
    resultado = "confirmamos tu pago" if confirmado else "no pudimos confirmar tu pago"
    motivo = "" if confirmado or not nota else f"\nMotivo: {nota}"
    return Mail(
        to=user.email,
        subject=f"Pago de la renta {renta.folio}",
        body=(
            f"Hola {user.full_name},\n\n"
            f"Ya {resultado} de la renta {renta.folio}.{motivo}\n\n"
            f"{_url(f'/cliente/rentas/{renta.id}')}"
        ),
    )


def rental_confirmed_mail(user: User, renta: Renta) -> Mail:
    return Mail(
        to=user.email,
        subject=f"Tu renta {renta.folio} está confirmada",
        body=(
            f"Hola {user.full_name},\n\n"
            f"Cumpliste los requisitos y recibimos tu anticipo: {renta.equipo.nombre} queda "
            f"confirmado para tu obra ({renta.folio}).\n"
            f"{_url(f'/cliente/rentas/{renta.id}')}"
        ),
    )


def _remaining(value: float, unit: str) -> str:
    if value <= 0:
        return f"se pasó por {abs(value):g} {unit}"
    return f"faltan {value:g} {unit}"


def maintenance_alert_mail(user: User, items: list[AtencionItem]) -> Mail:
    vencidos = [i for i in items if i.estado == "vencido"]
    lines = []
    for item in items:
        faltan = []
        if item.faltan_horas is not None:
            faltan.append(_remaining(float(item.faltan_horas), "h"))
        if item.faltan_dias is not None:
            faltan.append(_remaining(item.faltan_dias, "días"))
        marca = "VENCIDO" if item.estado == "vencido" else "Próximo"
        lines.append(
            f"- [{marca}] {item.equipo_codigo} {item.equipo_nombre}: {item.nombre} "
            f"({', '.join(faltan)}; horómetro {item.horometro_actual} h)"
        )
    resumen = f"{len(vencidos)} vencido(s)" if vencidos else f"{len(items)} próximo(s)"
    return Mail(
        to=user.email,
        subject=f"Mantenimiento de equipos: {resumen}",
        body=(
            f"Hola {user.full_name},\n\n"
            "Estos servicios de mantenimiento requieren atención:\n\n"
            + "\n".join(lines)
            + f"\n\nRegistra el servicio cuando se haga: {_url('/admin/mantenimiento')}"
        ),
    )

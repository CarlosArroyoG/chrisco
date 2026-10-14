"""Textos de los correos del sistema. Una función por correo; devuelven un `Mail` listo."""

from app.core.config import get_settings
from app.core.security import create_token
from app.models.empresa import Empresa
from app.models.user import User
from app.services.mailer import Mail


def _link(path: str, token: str) -> str:
    return f"{get_settings().frontend_url}/{path}?token={token}"


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

import json
import logging
import smtplib
from dataclasses import asdict, dataclass
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    def send(self, mail: Mail) -> None: ...


class ConsoleMailer:
    """Desarrollo: escribe el correo en el log en lugar de enviarlo."""

    def send(self, mail: Mail) -> None:
        logger.info("CORREO para %s | %s\n%s", mail.to, mail.subject, mail.body)


class FileMailer:
    """Desarrollo y pruebas E2E: agrega cada correo, como una línea JSON, a un archivo."""

    def send(self, mail: Mail) -> None:
        with get_settings().mail_outbox_file.open("a", encoding="utf-8") as outbox:
            outbox.write(json.dumps(asdict(mail), ensure_ascii=False) + "\n")


class SmtpMailer:
    def send(self, mail: Mail) -> None:
        s = get_settings()
        message = EmailMessage()
        message["From"] = s.mail_from
        message["To"] = mail.to
        message["Subject"] = mail.subject
        message.set_content(mail.body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_user and s.smtp_password:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(message)


@lru_cache
def get_mailer() -> Mailer:
    """Dependencia de FastAPI; las pruebas la sustituyen por un buzón en memoria."""
    backends: dict[str, Mailer] = {"smtp": SmtpMailer(), "file": FileMailer()}
    return backends.get(get_settings().mail_backend, ConsoleMailer())

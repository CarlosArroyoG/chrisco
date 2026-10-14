import json
import smtplib

import pytest

from app.core.config import get_settings
from app.services import mailer
from app.services.mailer import ConsoleMailer, FileMailer, Mail, SmtpMailer, get_mailer

MAIL = Mail(to="a@b.com", subject="Hola ñandú", body="Cuerpo\ncon salto")


def test_file_mailer_agrega_una_linea_json_por_correo(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "mail_outbox_file", tmp_path / "outbox.jsonl")
    FileMailer().send(MAIL)
    FileMailer().send(Mail(to="c@d.com", subject="Otro", body="x"))
    lines = (tmp_path / "outbox.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["to"] for line in lines] == ["a@b.com", "c@d.com"]
    assert json.loads(lines[0])["subject"] == "Hola ñandú"


def test_console_mailer_escribe_en_el_log(caplog) -> None:
    with caplog.at_level("INFO", logger="app.services.mailer"):
        ConsoleMailer().send(MAIL)
    assert "a@b.com" in caplog.text and "Cuerpo" in caplog.text


class FakeSmtp:
    instances: list["FakeSmtp"] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.calls: list[str] = []
        self.host, self.port = host, port
        FakeSmtp.instances.append(self)

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.calls.append(f"login:{user}")

    def send_message(self, message) -> None:  # noqa: ANN001
        self.calls.append(f"send:{message['To']}:{message['Subject']}")


@pytest.mark.parametrize(
    ("starttls", "user", "expected"),
    [
        (True, "u", ["starttls", "login:u", "send:a@b.com:Hola ñandú"]),
        (False, None, ["send:a@b.com:Hola ñandú"]),
    ],
)
def test_smtp_mailer(monkeypatch, starttls, user, expected) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_starttls", starttls)
    monkeypatch.setattr(settings, "smtp_user", user)
    monkeypatch.setattr(settings, "smtp_password", "p" if user else None)
    FakeSmtp.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    SmtpMailer().send(MAIL)
    assert FakeSmtp.instances[0].calls == expected


@pytest.mark.parametrize(
    ("backend", "kind"), [("console", ConsoleMailer), ("file", FileMailer), ("smtp", SmtpMailer)]
)
def test_get_mailer_elige_segun_la_configuracion(monkeypatch, backend, kind) -> None:
    monkeypatch.setattr(get_settings(), "mail_backend", backend)
    mailer.get_mailer.cache_clear()
    try:
        assert isinstance(get_mailer(), kind)
    finally:
        mailer.get_mailer.cache_clear()

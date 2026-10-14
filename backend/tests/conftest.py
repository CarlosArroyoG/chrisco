import os
import shutil
import tempfile

# Debe ir antes de importar la app: la configuración se lee una sola vez.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://chrisco:chrisco_dev@localhost:5433/chrisco_test"
)
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["UPLOADS_DIR"] = tempfile.mkdtemp(prefix="chrisco-uploads-")
os.environ.setdefault("SECRET_KEY", "clave-solo-para-pruebas-" + "x" * 16)

import re  # noqa: E402
from collections.abc import Callable, Iterator  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pwdlib import PasswordHash  # noqa: E402
from pwdlib.hashers.argon2 import Argon2Hasher  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core import security  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.empresa import Empresa, EmpresaStatus  # noqa: E402
from app.models.user import Role, User  # noqa: E402
from app.services import accounts  # noqa: E402
from app.services.mailer import Mail, get_mailer  # noqa: E402
from tests.probes import probe_router  # noqa: E402

app.include_router(probe_router)

# Argon2 con costo mínimo solo en las pruebas: el real es lento a propósito y multiplicaría el
# tiempo de la suite (cada usuario creado o autenticado lo paga). El resto del flujo no cambia.
security._password_hash = PasswordHash(
    (Argon2Hasher(time_cost=1, memory_cost=1024, parallelism=1),)
)
security._DUMMY_HASH = security._password_hash.hash("relleno")

PASSWORD = "contraseña-segura-123"
PDF = b"%PDF-1.4\n% constancia de prueba\n%%EOF"

COMPANY = {
    "razon_social": "Constructora Prueba SA de CV",
    "sitio_web": "constructora-prueba.com",
    "rfc": "CPR010101AB1",
    "full_name": "Titular Prueba",
    "email": "titular@constructora-prueba.com",
    "password": PASSWORD,
}


class Outbox(list[Mail]):
    """Buzón en memoria que sustituye al servicio de correo."""

    def send(self, mail: Mail) -> None:
        self.append(mail)

    def to(self, email: str) -> list[Mail]:
        return [m for m in self if m.to == email]


def token_from(mail: Mail) -> str:
    match = re.search(r"token=([\w.-]+)", mail.body)
    assert match, mail.body
    return match.group(1)


def auth(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def uploads_count(extension: str = "pdf") -> int:
    path = Path(get_settings().uploads_dir)
    return len(list(path.glob(f"*.{extension}"))) if path.exists() else 0


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> Iterator[None]:
    """Aplica las migraciones reales: así también se prueban."""
    command.upgrade(Config("alembic.ini"), "head")
    yield
    shutil.rmtree(get_settings().uploads_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users, empresas, categorias, equipos, equipo_fotos CASCADE"))
    shutil.rmtree(get_settings().uploads_dir, ignore_errors=True)


@pytest.fixture
def outbox() -> Iterator[Outbox]:
    box = Outbox()
    app.dependency_overrides[get_mailer] = lambda: box
    yield box
    app.dependency_overrides.pop(get_mailer, None)


@pytest.fixture
def client(outbox: Outbox) -> TestClient:
    return TestClient(app)


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    """Crea un usuario del personal (admin por defecto), con el correo ya verificado."""

    def _make(
        email: str = "admin@chrisco-pruebas.com", role: Role = Role.ADMIN, active: bool = True
    ) -> User:
        user = User(
            email=email,
            full_name="Usuario de prueba",
            role=role,
            password_hash=hash_password(PASSWORD),
            is_active=active,
            email_verified_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def login(client: TestClient) -> Callable[..., dict[str, str]]:
    def _login(
        email: str = "admin@chrisco-pruebas.com", password: str = PASSWORD
    ) -> dict[str, str]:
        res = client.post("/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        return res.json()

    return _login


@pytest.fixture
def register(client: TestClient) -> Callable[..., object]:
    """Registra una empresa por la API pública. Acepta overrides de campos y de la constancia."""

    def _register(constancia: bytes = PDF, **fields: str):  # noqa: ANN202
        return client.post(
            "/empresa/registro",
            data={**COMPANY, **fields},
            files={"constancia": ("constancia.pdf", constancia, "application/pdf")},
        )

    return _register


@pytest.fixture
def verify_email(db: Session) -> Callable[[str], None]:
    def _verify(email: str) -> None:
        user = accounts.get_by_email(db, email)
        assert user
        user.email_verified_at = datetime.now(UTC)
        db.commit()

    return _verify


@pytest.fixture
def set_company_status(db: Session) -> Callable[[str, EmpresaStatus], None]:
    def _set(rfc: str, status: EmpresaStatus) -> None:
        empresa = db.query(Empresa).filter_by(rfc=rfc).one()
        empresa.status = status
        db.commit()

    return _set


@pytest.fixture
def approved_owner(
    register: Callable[..., object],
    verify_email: Callable[[str], None],
    set_company_status: Callable[[str, EmpresaStatus], None],
) -> dict[str, str]:
    """Empresa aprobada con su titular verificado. Devuelve sus datos de acceso."""
    register()
    verify_email(COMPANY["email"])
    set_company_status(COMPANY["rfc"], EmpresaStatus.APROBADA)
    return {"email": COMPANY["email"], "password": PASSWORD}


@pytest.fixture
def admin_h(make_user: Callable[..., User], login: Callable[..., dict[str, str]]) -> dict[str, str]:
    make_user()
    return auth(login())


@pytest.fixture
def ventas_h(
    make_user: Callable[..., User], login: Callable[..., dict[str, str]]
) -> dict[str, str]:
    make_user("ventas@chrisco-pruebas.com", Role.VENTAS)
    return auth(login("ventas@chrisco-pruebas.com"))


@pytest.fixture
def client_h(
    approved_owner: dict[str, str], login: Callable[..., dict[str, str]]
) -> dict[str, str]:
    """Encabezados de un cliente de empresa aprobada."""
    return auth(login(**approved_owner))


CATEGORIA = {
    "nombre": "Pavimentadora",
    "spec_fields": [
        {"key": "peso_kg", "label": "Peso", "type": "number", "unit": "kg", "required": True},
        {"key": "motor", "label": "Motor", "type": "text"},
        {
            "key": "combustible",
            "label": "Combustible",
            "type": "select",
            "options": ["Diésel", "Gasolina"],
        },
        {"key": "oruga", "label": "Con orugas", "type": "boolean"},
    ],
}


@pytest.fixture
def categoria(client: TestClient, admin_h: dict[str, str]) -> dict[str, Any]:
    res = client.post("/admin/categorias", json=CATEGORIA, headers=admin_h)
    assert res.status_code == 201, res.text
    return res.json()


def equipo_payload(categoria_id: str, n: int = 1, **overrides: Any) -> dict[str, Any]:
    return {
        "codigo": f"EQ-{n:03d}",
        "categoria_id": categoria_id,
        "nombre": f"Pavimentadora {n}",
        "marca": "Vögele",
        "modelo": "MT 3000-2",
        "numero_serie": f"SN-{n:04d}",
        "anio": 2021,
        "horometro": 2400.5,
        "tarifa_hora": 3400,
        "specs": {"peso_kg": 18000, "motor": "Cummins 6.7", "combustible": "Diésel", "oruga": True},
        **overrides,
    }


@pytest.fixture
def make_equipo(
    client: TestClient, admin_h: dict[str, str], categoria: dict[str, Any]
) -> Callable[..., dict[str, Any]]:
    """Crea equipos por la API (códigos y series consecutivos). Devuelve el JSON del equipo."""
    counter = iter(range(1, 1000))

    def _make(**overrides: Any) -> dict[str, Any]:
        body = equipo_payload(categoria["id"], next(counter), **overrides)
        res = client.post("/admin/equipos", json=body, headers=admin_h)
        assert res.status_code == 201, res.text
        return res.json()

    return _make

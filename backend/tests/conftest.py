import os

# Debe ir antes de importar la app: la configuración se lee una sola vez.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://chrisco:chrisco_dev@localhost:5433/chrisco_test"
)
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ.setdefault("SECRET_KEY", "clave-solo-para-pruebas-" + "x" * 16)

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import Role, User  # noqa: E402

PASSWORD = "contraseña-segura-123"


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> None:
    """Aplica las migraciones reales: así también se prueban."""
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users CASCADE"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def make_user(db: Session):  # noqa: ANN201
    def _make(
        email: str = "admin@chrisco-pruebas.com", role: Role = Role.ADMIN, active: bool = True
    ) -> User:
        user = User(
            email=email,
            full_name="Usuario de prueba",
            role=role,
            password_hash=hash_password(PASSWORD),
            is_active=active,
        )
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def login(client: TestClient):  # noqa: ANN201
    def _login(email: str = "admin@chrisco-pruebas.com") -> dict[str, str]:
        res = client.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert res.status_code == 200, res.text
        return res.json()

    return _login

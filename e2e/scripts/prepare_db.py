"""Deja la base de datos E2E lista y vacía: la crea si falta, migra y borra los datos.

Se ejecuta con el entorno del backend: `uv run python ../e2e/scripts/prepare_db.py`
(DATABASE_URL debe apuntar a la base E2E).
"""

import subprocess
import sys

import psycopg
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def main() -> None:
    url = make_url(get_settings().database_url)
    database = url.database
    assert database and database.endswith("_e2e"), "La base E2E debe llamarse *_e2e (se borra su contenido)"

    maintenance = url.set(database="postgres").render_as_string(hide_password=False)
    with psycopg.connect(maintenance.replace("+psycopg", ""), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,)).fetchone()
        if not exists:
            conn.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(database)))

    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

    target = url.render_as_string(hide_password=False).replace("+psycopg", "")
    with psycopg.connect(target, autocommit=True) as conn:
        conn.execute("TRUNCATE users, empresas CASCADE")


if __name__ == "__main__":
    main()

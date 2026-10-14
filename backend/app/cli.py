"""Comandos de administración. Uso: uv run python -m app.cli create-user --help"""

import argparse
import getpass
import sys
from datetime import UTC, datetime

from app.core.security import MIN_PASSWORD_LENGTH, hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User
from app.services import accounts

# Los clientes no se crean aquí: se registran solos con su empresa.
STAFF_ROLES = [Role.ADMIN, Role.VENTAS, Role.OPERADOR]


def create_user(email: str, full_name: str, role: Role, password: str) -> None:
    with SessionLocal() as db:
        if accounts.get_by_email(db, email):
            sys.exit(f"Ya existe un usuario con el correo {email.lower()}")
        db.add(
            User(
                email=email.lower(),
                full_name=full_name,
                role=role,
                password_hash=hash_password(password),
                email_verified_at=datetime.now(UTC),
            )
        )
        db.commit()
    print(f"Usuario creado: {email.lower()} ({role.value})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    cu = sub.add_parser(
        "create-user", help="Crea un usuario del personal (admin, ventas, operador)"
    )
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", required=True, choices=[r.value for r in STAFF_ROLES])
    cu.add_argument("--password", help="Si se omite, se pide por teclado")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Contraseña: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres")
    create_user(args.email, args.name, Role(args.role), password)


if __name__ == "__main__":
    main()

"""Comandos de administración. Uso: uv run python -m app.cli create-user --help"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User


def create_user(email: str, full_name: str, role: Role, password: str) -> None:
    email = email.lower()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            sys.exit(f"Ya existe un usuario con el correo {email}")
        db.add(
            User(
                email=email,
                full_name=full_name,
                role=role,
                password_hash=hash_password(password),
            )
        )
        db.commit()
    print(f"Usuario creado: {email} ({role.value})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    cu = sub.add_parser("create-user", help="Crea un usuario")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", required=True, choices=[r.value for r in Role])
    cu.add_argument("--password", help="Si se omite, se pide por teclado")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Contraseña: ")
    if len(password) < 10:
        sys.exit("La contraseña debe tener al menos 10 caracteres")
    create_user(args.email, args.name, Role(args.role), password)


if __name__ == "__main__":
    main()

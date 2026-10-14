"""empresas y verificacion de correo

Revision ID: 7156d33208d8
Revises: 8469e6e1a421
Create Date: 2026-10-13 22:25:07.730883

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7156d33208d8"
down_revision: str | Sequence[str] | None = "8469e6e1a421"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "empresas",
        sa.Column("razon_social", sa.String(length=200), nullable=False),
        sa.Column("sitio_web", sa.String(length=255), nullable=False),
        sa.Column("rfc", sa.String(length=13), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pendiente", "aprobada", "rechazada", name="empresa_status"),
            nullable=False,
        ),
        sa.Column("motivo_rechazo", sa.Text(), nullable=True),
        sa.Column("constancia_key", sa.String(length=100), nullable=False),
        sa.Column("reviewed_by_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"], ["users.id"], name=op.f("fk_empresas_reviewed_by_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_empresas")),
    )
    op.create_index(op.f("ix_empresas_rfc"), "empresas", ["rfc"], unique=True)

    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("empresa_id", sa.Uuid(), nullable=True))
    op.add_column(
        "users", sa.Column("is_company_owner", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.create_foreign_key(
        op.f("fk_users_empresa_id_empresas"), "users", "empresas", ["empresa_id"], ["id"], ondelete="RESTRICT"
    )
    # Los usuarios que ya existen los creó un administrador: su correo cuenta como verificado.
    op.execute("UPDATE users SET email_verified_at = now() WHERE email_verified_at IS NULL")
    op.create_check_constraint(
        "cliente_tiene_empresa", "users", "(role = 'cliente') = (empresa_id IS NOT NULL)"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_cliente_tiene_empresa"), "users", type_="check")
    op.drop_constraint(op.f("fk_users_empresa_id_empresas"), "users", type_="foreignkey")
    op.drop_column("users", "is_company_owner")
    op.drop_column("users", "empresa_id")
    op.drop_column("users", "email_verified_at")
    op.drop_index(op.f("ix_empresas_rfc"), table_name="empresas")
    op.drop_table("empresas")
    sa.Enum(name="empresa_status").drop(op.get_bind(), checkfirst=True)

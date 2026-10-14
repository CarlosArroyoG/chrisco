"""documentos y pagos

Revision ID: e21686f25e28
Revises: 8137a8bea5dc
Create Date: 2026-10-14 01:49:35.287204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e21686f25e28'
down_revision: Union[str, Sequence[str], None] = '8137a8bea5dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # El mismo tipo lo usan dos tablas: se crea una vez y las tablas lo reutilizan.
    revision_estado = postgresql.ENUM(
        "pendiente", "aprobado", "rechazado", name="revision_estado", create_type=False
    )
    revision_estado.create(op.get_bind(), checkfirst=True)
    op.create_table('pagos',
    sa.Column('renta_id', sa.Uuid(), nullable=False),
    sa.Column('monto', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('fecha_pago', sa.Date(), nullable=False),
    sa.Column('referencia', sa.String(length=60), nullable=True),
    sa.Column('comprobante_key', sa.String(length=100), nullable=False),
    sa.Column('estado', revision_estado, nullable=False),
    sa.Column('nota_revision', sa.Text(), nullable=True),
    sa.Column('reportado_por_id', sa.Uuid(), nullable=False),
    sa.Column('revisado_por_id', sa.Uuid(), nullable=True),
    sa.Column('revisado_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('monto > 0', name=op.f('ck_pagos_monto_positivo')),
    sa.ForeignKeyConstraint(['renta_id'], ['rentas.id'], name=op.f('fk_pagos_renta_id_rentas'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reportado_por_id'], ['users.id'], name=op.f('fk_pagos_reportado_por_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['revisado_por_id'], ['users.id'], name=op.f('fk_pagos_revisado_por_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pagos'))
    )
    op.create_index(op.f('ix_pagos_renta_id'), 'pagos', ['renta_id'], unique=False)
    op.create_table('renta_documentos',
    sa.Column('renta_id', sa.Uuid(), nullable=False),
    sa.Column('requisito', sa.String(length=40), nullable=False),
    sa.Column('filename', sa.String(length=200), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('estado', revision_estado, nullable=False),
    sa.Column('nota_revision', sa.Text(), nullable=True),
    sa.Column('subido_por_id', sa.Uuid(), nullable=False),
    sa.Column('revisado_por_id', sa.Uuid(), nullable=True),
    sa.Column('revisado_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['renta_id'], ['rentas.id'], name=op.f('fk_renta_documentos_renta_id_rentas'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['revisado_por_id'], ['users.id'], name=op.f('fk_renta_documentos_revisado_por_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['subido_por_id'], ['users.id'], name=op.f('fk_renta_documentos_subido_por_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_renta_documentos'))
    )
    op.create_index(op.f('ix_renta_documentos_renta_id'), 'renta_documentos', ['renta_id'], unique=False)
    op.add_column('rentas', sa.Column('condiciones_verificadas', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rentas', 'condiciones_verificadas')
    op.drop_index(op.f('ix_renta_documentos_renta_id'), table_name='renta_documentos')
    op.drop_table('renta_documentos')
    op.drop_index(op.f('ix_pagos_renta_id'), table_name='pagos')
    op.drop_table('pagos')
    sa.Enum(name='revision_estado').drop(op.get_bind(), checkfirst=True)

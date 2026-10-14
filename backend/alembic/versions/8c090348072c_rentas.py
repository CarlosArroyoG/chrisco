"""rentas

Revision ID: 8c090348072c
Revises: e7da6725fb24
Create Date: 2026-10-14 00:01:42.486645

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8c090348072c'
down_revision: Union[str, Sequence[str], None] = 'e7da6725fb24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SEQUENCE renta_folio_seq")
    op.create_table('rentas',
    sa.Column('folio', sa.String(length=20), nullable=False),
    sa.Column('estado', sa.Enum('solicitada', 'cotizada', 'apartada', 'confirmada', 'en_renta', 'devuelta', 'cerrada', 'vencida', 'cancelada', 'rechazada', name='renta_estado'), nullable=False),
    sa.Column('empresa_id', sa.Uuid(), nullable=False),
    sa.Column('solicitante_id', sa.Uuid(), nullable=False),
    sa.Column('equipo_id', sa.Uuid(), nullable=False),
    sa.Column('bloqueo_id', sa.Uuid(), nullable=True),
    sa.Column('desde', sa.DateTime(timezone=True), nullable=False),
    sa.Column('hasta', sa.DateTime(timezone=True), nullable=False),
    sa.Column('destino', sa.String(length=200), nullable=False),
    sa.Column('operador_modo', sa.Enum('chrisco', 'cliente', name='operador_modo'), nullable=False),
    sa.Column('transporte', sa.Enum('entrega', 'recoge', name='transporte'), nullable=False),
    sa.Column('notas', sa.Text(), nullable=True),
    sa.Column('requisitos', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('hasta > desde', name=op.f('ck_rentas_periodo_valido')),
    sa.ForeignKeyConstraint(['bloqueo_id'], ['bloqueos.id'], name=op.f('fk_rentas_bloqueo_id_bloqueos'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], name=op.f('fk_rentas_empresa_id_empresas'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['equipo_id'], ['equipos.id'], name=op.f('fk_rentas_equipo_id_equipos'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['solicitante_id'], ['users.id'], name=op.f('fk_rentas_solicitante_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rentas')),
    sa.UniqueConstraint('bloqueo_id', name=op.f('uq_rentas_bloqueo_id')),
    sa.UniqueConstraint('folio', name=op.f('uq_rentas_folio'))
    )
    op.create_index(op.f('ix_rentas_empresa_id'), 'rentas', ['empresa_id'], unique=False)
    op.create_index(op.f('ix_rentas_equipo_id'), 'rentas', ['equipo_id'], unique=False)
    op.create_index(op.f('ix_rentas_estado'), 'rentas', ['estado'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_rentas_estado'), table_name='rentas')
    op.drop_index(op.f('ix_rentas_equipo_id'), table_name='rentas')
    op.drop_index(op.f('ix_rentas_empresa_id'), table_name='rentas')
    op.drop_table('rentas')
    for name in ('renta_estado', 'operador_modo', 'transporte'):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
    op.execute("DROP SEQUENCE renta_folio_seq")

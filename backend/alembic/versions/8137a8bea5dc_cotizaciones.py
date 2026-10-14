"""cotizaciones

Revision ID: 8137a8bea5dc
Revises: 8c090348072c
Create Date: 2026-10-14 00:34:43.739994

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8137a8bea5dc'
down_revision: Union[str, Sequence[str], None] = '8c090348072c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('cotizaciones',
    sa.Column('renta_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('estado', sa.Enum('vigente', 'aceptada', 'rechazada', 'reemplazada', 'vencida', name='cotizacion_estado'), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('iva', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('anticipo_monto', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('valida_hasta', sa.DateTime(timezone=True), nullable=False),
    sa.Column('notas', sa.Text(), nullable=True),
    sa.Column('creada_por_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('anticipo_monto >= 0 AND anticipo_monto <= total', name=op.f('ck_cotizaciones_anticipo_valido')),
    sa.CheckConstraint('total = subtotal + iva', name=op.f('ck_cotizaciones_total_cuadra')),
    sa.ForeignKeyConstraint(['creada_por_id'], ['users.id'], name=op.f('fk_cotizaciones_creada_por_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['renta_id'], ['rentas.id'], name=op.f('fk_cotizaciones_renta_id_rentas'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cotizaciones'))
    )
    op.create_index(op.f('ix_cotizaciones_renta_id'), 'cotizaciones', ['renta_id'], unique=False)
    op.create_index('uq_cotizaciones_viva_por_renta', 'cotizaciones', ['renta_id'], unique=True, postgresql_where=sa.text("estado IN ('vigente', 'aceptada')"))
    op.create_table('cotizacion_partidas',
    sa.Column('cotizacion_id', sa.Uuid(), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('concepto', sa.Enum('renta', 'flete', 'trailer', 'combustible', 'operador', 'seguro', 'otro', name='partida_concepto'), nullable=False),
    sa.Column('descripcion', sa.String(length=200), nullable=False),
    sa.Column('cantidad', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('unidad', sa.Enum('hora', 'dia', 'viaje', 'litro', 'servicio', name='partida_unidad'), nullable=False),
    sa.Column('precio_unitario', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('importe', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('cantidad > 0', name=op.f('ck_cotizacion_partidas_cantidad_positiva')),
    sa.CheckConstraint('precio_unitario >= 0', name=op.f('ck_cotizacion_partidas_precio_no_negativo')),
    sa.ForeignKeyConstraint(['cotizacion_id'], ['cotizaciones.id'], name=op.f('fk_cotizacion_partidas_cotizacion_id_cotizaciones'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cotizacion_partidas'))
    )
    op.create_index(op.f('ix_cotizacion_partidas_cotizacion_id'), 'cotizacion_partidas', ['cotizacion_id'], unique=False)
    op.add_column('rentas', sa.Column('motivo_cierre', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rentas', 'motivo_cierre')
    op.drop_index(op.f('ix_cotizacion_partidas_cotizacion_id'), table_name='cotizacion_partidas')
    op.drop_table('cotizacion_partidas')
    op.drop_index('uq_cotizaciones_viva_por_renta', table_name='cotizaciones', postgresql_where=sa.text("estado IN ('vigente', 'aceptada')"))
    op.drop_index(op.f('ix_cotizaciones_renta_id'), table_name='cotizaciones')
    op.drop_table('cotizaciones')
    for name in ('cotizacion_estado', 'partida_concepto', 'partida_unidad'):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)

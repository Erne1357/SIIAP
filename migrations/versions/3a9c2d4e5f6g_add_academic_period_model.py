"""add academic period model

Revision ID: 3a9c2d4e5f6g
Revises: 2f8a9c1b4d7e
Create Date: 2026-01-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a9c2d4e5f6g'
down_revision = '2f8a9c1b4d7e'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla academic_period
    op.create_table('academic_period',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=5), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('admission_start_date', sa.Date(), nullable=False),
        sa.Column('admission_end_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=False),
        sa.Column('status', sa.String(length=20), nullable=False, default='upcoming'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    # Crear indice para busquedas rapidas por is_active
    op.create_index('ix_academic_period_is_active', 'academic_period', ['is_active'])


def downgrade():
    op.drop_index('ix_academic_period_is_active', table_name='academic_period')
    op.drop_table('academic_period')

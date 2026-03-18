"""add archive.validity_months

Revision ID: 2j8l0m2n3o4p
Revises: 1i7k9l0m1n2o
Create Date: 2026-03-18 13:00:00.000000

Agrega validity_months a la tabla archive.
NULL = sin vencimiento (válido indefinidamente).
Valor en meses: p.ej. 6 = el doc expira 6 meses después de su fecha de subida.
"""
from alembic import op
import sqlalchemy as sa

revision = '2j8l0m2n3o4p'
down_revision = '1i7k9l0m1n2o'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'archive',
        sa.Column('validity_months', sa.Integer(), nullable=True)
    )


def downgrade():
    op.drop_column('archive', 'validity_months')

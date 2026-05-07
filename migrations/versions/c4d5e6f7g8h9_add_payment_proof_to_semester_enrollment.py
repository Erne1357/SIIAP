"""add_payment_proof_path_to_semester_enrollment

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-04-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4d5e6f7g8h9'
down_revision = 'b3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'semester_enrollment',
        sa.Column('payment_proof_path', sa.String(length=255), nullable=True),
    )


def downgrade():
    op.drop_column('semester_enrollment', 'payment_proof_path')

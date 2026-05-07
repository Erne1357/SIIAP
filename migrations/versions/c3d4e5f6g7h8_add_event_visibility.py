"""add_event_visibility

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-04-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('event', sa.Column('visibility', sa.String(20), nullable=False, server_default='public'))


def downgrade():
    op.drop_column('event', 'visibility')

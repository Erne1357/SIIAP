"""add_reminders_enabled_to_event

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-04-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('event', sa.Column('reminders_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column('event', 'reminders_enabled')

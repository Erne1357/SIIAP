"""add_last_events_seen_at_to_user

Revision ID: b3c4d5e6f7g8
Revises: e5f6g7h8i9j0
Create Date: 2026-04-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7g8'
down_revision = 'e5f6g7h8i9j0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('last_events_seen_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('user', 'last_events_seen_at')

"""add_photo_change_flags_to_user

Adds photo_change_allowed (Boolean) and photo_change_requested_at (DateTime)
to the user table for the profile photo change-request workflow:
  - Coordinator enables photo change → photo_change_allowed=True
  - Student uploads → flag resets to False
  - Student requests change → photo_change_requested_at=now

Revision ID: f1a2b3c4d5e6
Revises: e1f2g3h4i5j6
Create Date: 2026-05-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f1a2b3c4d5e6'
down_revision = 'e1f2g3h4i5j6'
branch_labels = None
depends_on = None


def upgrade():
    # server_default kept so raw SQL INSERTs (test data, manual ops) don't fail.
    # ORM inserts already use the SQLAlchemy `default=False` from the model.
    op.add_column('user', sa.Column(
        'photo_change_allowed', sa.Boolean(),
        nullable=False, server_default=sa.text('false'),
    ))
    op.add_column('user', sa.Column(
        'photo_change_requested_at', sa.DateTime(), nullable=True,
    ))


def downgrade():
    op.drop_column('user', 'photo_change_requested_at')
    op.drop_column('user', 'photo_change_allowed')

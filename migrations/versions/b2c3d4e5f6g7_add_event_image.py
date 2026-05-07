"""add_event_image

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_image',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('path', sa.String(500), nullable=False),
        sa.Column('caption', sa.String(200), nullable=True),
        sa.Column('is_cover', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['event.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_event_image_event_id', 'event_image', ['event_id'])


def downgrade():
    op.drop_index('ix_event_image_event_id', table_name='event_image')
    op.drop_table('event_image')

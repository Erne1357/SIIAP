"""add_event_host

Revision ID: a1b2c3d4e5f6
Revises: 9q7u9v0w1x2y
Create Date: 2026-04-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '9q7u9v0w1x2y'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_host',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('external_name', sa.String(150), nullable=True),
        sa.Column('external_bio', sa.Text(), nullable=True),
        sa.Column('external_photo_path', sa.String(255), nullable=True),
        sa.Column('role_label', sa.String(100), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['event.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            '(user_id IS NOT NULL) OR (external_name IS NOT NULL)',
            name='ck_event_host_identity'
        ),
    )
    op.create_index('ix_event_host_event_id', 'event_host', ['event_id'])


def downgrade():
    op.drop_index('ix_event_host_event_id', table_name='event_host')
    op.drop_table('event_host')

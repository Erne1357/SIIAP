"""add_event_reminder_log

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-04-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_reminder_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=True),
        sa.Column('reminder_type', sa.String(10), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['event.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointment.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'event_id', 'user_id', 'reminder_type', 'appointment_id',
            name='uq_event_reminder_once'
        ),
    )
    op.create_index('ix_event_reminder_lookup', 'event_reminder_log', ['event_id', 'user_id', 'reminder_type'])


def downgrade():
    op.drop_index('ix_event_reminder_lookup', table_name='event_reminder_log')
    op.drop_table('event_reminder_log')

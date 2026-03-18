"""add enrollment_deferral table

Revision ID: 0h6j7k8l9m0n
Revises: 9g5i6j7k8l9m
Create Date: 2026-03-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '0h6j7k8l9m0n'
down_revision = '9g5i6j7k8l9m'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'enrollment_deferral',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_program_id', sa.Integer(), nullable=False),
        sa.Column('original_period_id', sa.Integer(), nullable=False),
        sa.Column('deferred_to_period_id', sa.Integer(), nullable=True),
        sa.Column('deferral_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('requested_by', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expiry_notified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_program_id'], ['user_program.id']),
        sa.ForeignKeyConstraint(['original_period_id'], ['academic_period.id']),
        sa.ForeignKeyConstraint(['deferred_to_period_id'], ['academic_period.id']),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_enrollment_deferral_user_program_id',
        'enrollment_deferral',
        ['user_program_id'],
    )
    op.create_index(
        'ix_enrollment_deferral_status',
        'enrollment_deferral',
        ['status'],
    )


def downgrade():
    op.drop_index('ix_enrollment_deferral_status', table_name='enrollment_deferral')
    op.drop_index('ix_enrollment_deferral_user_program_id', table_name='enrollment_deferral')
    op.drop_table('enrollment_deferral')

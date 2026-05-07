"""add_purge_run_table

Revision ID: e1f2g3h4i5j6
Revises: c4d5e6f7g8h9
Create Date: 2026-04-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e1f2g3h4i5j6'
down_revision = 'c4d5e6f7g8h9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'purge_run',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.String(length=36), nullable=False, unique=True),
        sa.Column('initiated_by', sa.Integer(), nullable=False),
        sa.Column('initiated_at', sa.DateTime(), nullable=False),
        sa.Column('purge_type', sa.String(length=40), nullable=False),
        sa.Column('source_period_id', sa.Integer(), nullable=True),
        sa.Column('target_period_id', sa.Integer(), nullable=True),
        sa.Column('program_id', sa.Integer(), nullable=True),
        sa.Column('target_user_program_ids', sa.JSON(), nullable=False),
        sa.Column('archive_path', sa.String(length=500), nullable=True),
        sa.Column('archive_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('archive_sha256', sa.String(length=64), nullable=True),
        sa.Column('archive_downloaded_at', sa.DateTime(), nullable=True),
        sa.Column('purged_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending_download'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['initiated_by'], ['user.id'], name='fk_purge_run_initiated_by'),
        sa.ForeignKeyConstraint(['source_period_id'], ['academic_period.id'], name='fk_purge_run_source_period'),
        sa.ForeignKeyConstraint(['target_period_id'], ['academic_period.id'], name='fk_purge_run_target_period'),
        sa.ForeignKeyConstraint(['program_id'], ['program.id'], name='fk_purge_run_program'),
    )
    op.create_index('ix_purge_run_run_id', 'purge_run', ['run_id'], unique=True)
    op.create_index('ix_purge_run_purge_type', 'purge_run', ['purge_type'])
    op.create_index('ix_purge_run_status', 'purge_run', ['status'])


def downgrade():
    op.drop_index('ix_purge_run_status', table_name='purge_run')
    op.drop_index('ix_purge_run_purge_type', table_name='purge_run')
    op.drop_index('ix_purge_run_run_id', table_name='purge_run')
    op.drop_table('purge_run')

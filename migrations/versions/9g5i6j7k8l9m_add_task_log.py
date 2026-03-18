"""add task_log table

Revision ID: 9g5i6j7k8l9m
Revises: 8f4h5i6j7k8l
Create Date: 2026-03-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '9g5i6j7k8l9m'
down_revision = '8f4h5i6j7k8l'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'task_logs',
        sa.Column('id',                    sa.Integer(),     nullable=False),
        sa.Column('task_id',               sa.String(255),   nullable=False),
        sa.Column('task_name',             sa.String(255),   nullable=False),
        sa.Column('status',                sa.String(20),    nullable=False, server_default='pending'),
        sa.Column('triggered_by',          sa.String(20),    nullable=False, server_default='scheduled'),
        sa.Column('triggered_by_user_id',  sa.Integer(),     nullable=True),
        sa.Column('started_at',            sa.DateTime(),    nullable=True),
        sa.Column('finished_at',           sa.DateTime(),    nullable=True),
        sa.Column('kwargs',                sa.JSON(),        nullable=True),
        sa.Column('result',                sa.JSON(),        nullable=True),
        sa.Column('error_message',         sa.Text(),        nullable=True),
        sa.Column('created_at',            sa.DateTime(),    nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id'),
    )
    op.create_index('ix_task_logs_task_id',   'task_logs', ['task_id'],   unique=True)
    op.create_index('ix_task_logs_task_name', 'task_logs', ['task_name'], unique=False)
    op.create_index('ix_task_logs_status',    'task_logs', ['status'],    unique=False)


def downgrade():
    op.drop_index('ix_task_logs_status',    table_name='task_logs')
    op.drop_index('ix_task_logs_task_name', table_name='task_logs')
    op.drop_index('ix_task_logs_task_id',   table_name='task_logs')
    op.drop_table('task_logs')

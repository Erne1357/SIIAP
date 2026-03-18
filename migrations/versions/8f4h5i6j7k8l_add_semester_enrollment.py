"""add semester enrollment

Revision ID: 8f4h5i6j7k8l
Revises: 7e3g6h8i0j1k
Create Date: 2026-03-17 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f4h5i6j7k8l'
down_revision = '7e3g6h8i0j1k'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'semester_enrollment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_program_id', sa.Integer(), nullable=False),
        sa.Column('academic_period_id', sa.Integer(), nullable=False),
        sa.Column('semester_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='pending'),
        sa.Column('enrollment_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('confirmed_by', sa.Integer(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('documents_deadline', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_program_id'], ['user_program.id'], ),
        sa.ForeignKeyConstraint(['academic_period_id'], ['academic_period.id'], ),
        sa.ForeignKeyConstraint(['confirmed_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_program_id', 'academic_period_id',
                            name='uq_semester_enrollment_up_period'),
    )
    op.create_index('ix_semester_enrollment_user_program_id',
                    'semester_enrollment', ['user_program_id'])
    op.create_index('ix_semester_enrollment_academic_period_id',
                    'semester_enrollment', ['academic_period_id'])


def downgrade():
    op.drop_index('ix_semester_enrollment_academic_period_id',
                  table_name='semester_enrollment')
    op.drop_index('ix_semester_enrollment_user_program_id',
                  table_name='semester_enrollment')
    op.drop_table('semester_enrollment')

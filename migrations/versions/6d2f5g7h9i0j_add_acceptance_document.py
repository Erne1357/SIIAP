"""add acceptance_document table

Revision ID: 6d2f5g7h9i0j
Revises: 5c1e4f6g8h9j
Create Date: 2026-03-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d2f5g7h9i0j'
down_revision = '5c1e4f6g8h9j'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'acceptance_document',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_program_id', sa.Integer(), nullable=False),
        sa.Column('document_type', sa.String(30), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('uploaded_by_id', sa.Integer(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_program_id'], ['user_program.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by_id'], ['user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['user.id'], ondelete='SET NULL'),
    )

    op.create_index('ix_acceptance_document_user_program_id', 'acceptance_document', ['user_program_id'])
    op.create_index('ix_acceptance_document_document_type', 'acceptance_document', ['document_type'])
    op.create_index('ix_acceptance_document_status', 'acceptance_document', ['status'])


def downgrade():
    op.drop_index('ix_acceptance_document_status', table_name='acceptance_document')
    op.drop_index('ix_acceptance_document_document_type', table_name='acceptance_document')
    op.drop_index('ix_acceptance_document_user_program_id', table_name='acceptance_document')
    op.drop_table('acceptance_document')

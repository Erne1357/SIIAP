"""add document_template table

Revision ID: 3k0n2o3p4q5r
Revises: 2j8l0m2n3o4p
Create Date: 2026-03-20 10:00:00.000000

Tabla para gestionar plantillas de documentos institucionales
(cartas de aceptación, confirmaciones de inscripción, horarios, etc.)
"""
from alembic import op
import sqlalchemy as sa

revision = '3k0n2o3p4q5r'
down_revision = '2j8l0m2n3o4p'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'document_template',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=True),
        sa.Column('document_type', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('file_type', sa.String(10), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['program_id'], ['program.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_template_document_type', 'document_template', ['document_type'])
    op.create_index('ix_document_template_program_id', 'document_template', ['program_id'])


def downgrade():
    op.drop_index('ix_document_template_program_id', table_name='document_template')
    op.drop_index('ix_document_template_document_type', table_name='document_template')
    op.drop_table('document_template')

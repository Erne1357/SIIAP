"""add document_deadline table

Revision ID: 6n4r6s7t8u9v
Revises: 5m3q5r6s7t8u
Create Date: 2026-03-24 00:00:00.000000

Crea la tabla document_deadline para gestionar las ventanas de entrega
de documentos de permanencia semestral (Módulo B y C — Permanencia).

El coordinador crea ventanas por archive + programa + periodo. Los estudiantes
suben documentos dentro del rango opens_at/closes_at o mientras is_open=True.
"""
from alembic import op
import sqlalchemy as sa

revision = '6n4r6s7t8u9v'
down_revision = '5m3q5r6s7t8u'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'document_deadline',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('archive_id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('academic_period_id', sa.Integer(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('opens_at', sa.DateTime(), nullable=True),
        sa.Column('closes_at', sa.DateTime(), nullable=True),
        sa.Column('is_open', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['archive_id'], ['archive.id']),
        sa.ForeignKeyConstraint(['program_id'], ['program.id']),
        sa.ForeignKeyConstraint(['academic_period_id'], ['academic_period.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_deadline_program_period',
                    'document_deadline', ['program_id', 'academic_period_id'])


def downgrade():
    op.drop_index('ix_document_deadline_program_period', table_name='document_deadline')
    op.drop_table('document_deadline')

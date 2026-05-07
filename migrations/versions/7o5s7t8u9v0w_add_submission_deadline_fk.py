"""add submission.document_deadline_id FK

Revision ID: 7o5s7t8u9v0w
Revises: 6n4r6s7t8u9v
Create Date: 2026-03-24 00:00:00.000000

Agrega la FK document_deadline_id a la tabla submission.
Solo se llena para submissions de permanencia vinculadas a una ventana de entrega.
Submissions de admisión y otras fases quedan con NULL.
"""
from alembic import op
import sqlalchemy as sa

revision = '7o5s7t8u9v0w'
down_revision = '6n4r6s7t8u9v'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'submission',
        sa.Column('document_deadline_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_submission_document_deadline',
        'submission', 'document_deadline',
        ['document_deadline_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('fk_submission_document_deadline', 'submission', type_='foreignkey')
    op.drop_column('submission', 'document_deadline_id')

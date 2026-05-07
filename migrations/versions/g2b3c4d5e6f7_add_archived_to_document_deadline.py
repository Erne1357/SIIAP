"""add_archived_flags_to_document_deadline

Adds soft-archive columns to document_deadline:
  - is_archived (Boolean, default False)
  - archived_at (DateTime nullable)
  - archived_by (Integer FK user.id nullable)

This replaces hard-delete with soft-archive so submissions linked to a
deadline keep their reference (FK integrity + audit trail).

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'g2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('document_deadline', sa.Column(
        'is_archived', sa.Boolean(),
        nullable=False, server_default=sa.text('false'),
    ))
    op.add_column('document_deadline', sa.Column(
        'archived_at', sa.DateTime(), nullable=True,
    ))
    op.add_column('document_deadline', sa.Column(
        'archived_by', sa.Integer(), nullable=True,
    ))
    op.create_foreign_key(
        'fk_document_deadline_archived_by',
        'document_deadline', 'user',
        ['archived_by'], ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint('fk_document_deadline_archived_by', 'document_deadline', type_='foreignkey')
    op.drop_column('document_deadline', 'archived_by')
    op.drop_column('document_deadline', 'archived_at')
    op.drop_column('document_deadline', 'is_archived')

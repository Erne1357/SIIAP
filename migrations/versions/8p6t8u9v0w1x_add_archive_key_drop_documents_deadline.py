"""add_archive_key_drop_documents_deadline

Revision ID: 8p6t8u9v0w1x
Revises: 135a97882bf7
Create Date: 2026-04-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8p6t8u9v0w1x'
down_revision = '135a97882bf7'
branch_labels = None
depends_on = None


def upgrade():
    # Add archive_key column to archive table
    op.add_column('archive',
        sa.Column('archive_key', sa.String(50), nullable=True)
    )
    op.create_unique_constraint('uq_archive_archive_key', 'archive', ['archive_key'])

    # Drop orphaned documents_deadline column from semester_enrollment
    op.drop_column('semester_enrollment', 'documents_deadline')


def downgrade():
    # Restore documents_deadline column
    op.add_column('semester_enrollment',
        sa.Column('documents_deadline', sa.DateTime(), nullable=True)
    )

    # Remove archive_key column
    op.drop_constraint('uq_archive_archive_key', 'archive', type_='unique')
    op.drop_column('archive', 'archive_key')

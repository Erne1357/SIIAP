"""condition resolved by submission

Revision ID: s4n5o6p7q8r9
Revises: r3m4n5o6p7q8
Create Date: 2026-10-27

Phase 6D: an admission condition met automatically (its conclusion
requirement was approved in the review inbox) remembers the submission whose
approval met it, `admission_condition.resolved_by_submission_id` (FK
`submission.id`, SET NULL, indexed). Reverting that approval reopens exactly
the conditions it met; a condition resolved by hand keeps NULL and is never
reopened.

Expand-only: a new nullable column the previous color neither reads nor
writes. Creation is skipped when the column already exists; downgrade drops it.
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 's4n5o6p7q8r9'
down_revision = 'r3m4n5o6p7q8'
branch_labels = None
depends_on = None

TABLE = 'admission_condition'
COLUMN = 'resolved_by_submission_id'
FK_NAME = 'fk_admission_condition_resolved_by_submission_id'
INDEX_NAME = 'ix_admission_condition_resolved_by_submission_id'


def _columns():
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade():
    if COLUMN in _columns():
        return
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(sa.Column(COLUMN, sa.Integer(), nullable=True))
        batch.create_foreign_key(FK_NAME, 'submission', [COLUMN], ['id'], ondelete='SET NULL')
        batch.create_index(INDEX_NAME, [COLUMN])


def downgrade():
    if COLUMN not in _columns():
        return
    inspector = sa.inspect(op.get_bind())
    indexes = {i['name'] for i in inspector.get_indexes(TABLE)}
    fks = {f['name'] for f in inspector.get_foreign_keys(TABLE) if f.get('name')}
    with op.batch_alter_table(TABLE) as batch:
        if INDEX_NAME in indexes:
            batch.drop_index(INDEX_NAME)
        if FK_NAME in fks:
            batch.drop_constraint(FK_NAME, type_='foreignkey')
        batch.drop_column(COLUMN)

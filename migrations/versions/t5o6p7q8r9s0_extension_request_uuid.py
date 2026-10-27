"""extension_request public uuid

Revision ID: t5o6p7q8r9s0
Revises: s4n5o6p7q8r9
Create Date: 2026-10-27

Phase 6D: `extension_request` gets a public `uuid` (PublicUUIDMixin) so the
review inbox addresses every kind by uuid and no integer id reaches a URL.

Blue-green safe: the previous color keeps inserting rows without knowing the
column for about a minute. On PostgreSQL the column is therefore added as
`uuid NOT NULL DEFAULT gen_random_uuid()`: the default fills the existing rows
and any insert from the old color. The server default is kept on purpose (the
new color still sets a uuid7 from the Python column default). A unique index
`ix_extension_request_uuid` follows.

Other dialects (SQLite in tests): the column is added nullable, backfilled in
Python with uuid7, then made NOT NULL and indexed.

Creation is skipped when the column already exists; downgrade drops index and
column.
"""
import sqlalchemy as sa
from alembic import op

from app.utils.uuid7 import uuid7


# revision identifiers, used by Alembic.
revision = 't5o6p7q8r9s0'
down_revision = 's4n5o6p7q8r9'
branch_labels = None
depends_on = None

TABLE = 'extension_request'
COLUMN = 'uuid'
INDEX_NAME = 'ix_extension_request_uuid'


def _columns():
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade():
    if COLUMN in _columns():
        return
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.add_column(TABLE, sa.Column(
            COLUMN, sa.Uuid(as_uuid=True), nullable=False,
            server_default=sa.text('gen_random_uuid()')))
        op.create_index(INDEX_NAME, TABLE, [COLUMN], unique=True)
        return

    op.add_column(TABLE, sa.Column(COLUMN, sa.Uuid(as_uuid=True), nullable=True))
    table = sa.table(TABLE, sa.column('id', sa.Integer),
                     sa.column(COLUMN, sa.Uuid(as_uuid=True)))
    for (row_id,) in bind.execute(sa.select(table.c.id)).fetchall():
        bind.execute(table.update().where(table.c.id == row_id).values({COLUMN: uuid7()}))
    with op.batch_alter_table(TABLE) as batch:
        batch.alter_column(COLUMN, existing_type=sa.Uuid(as_uuid=True), nullable=False)
        batch.create_index(INDEX_NAME, [COLUMN], unique=True)


def downgrade():
    if COLUMN not in _columns():
        return
    indexes = {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(TABLE)}
    with op.batch_alter_table(TABLE) as batch:
        if INDEX_NAME in indexes:
            batch.drop_index(INDEX_NAME)
        batch.drop_column(COLUMN)

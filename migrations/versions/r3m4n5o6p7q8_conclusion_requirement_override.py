"""conclusion requirement override

Revision ID: r3m4n5o6p7q8
Revises: q2l3m4n5o6p7
Create Date: 2026-10-22

Phase 6C, owner's decisions 6-7: the coordination may mark a conclusion
requirement "no aplica" for one student, or accept a reused admission
document whose validity lapsed. Both are rows of the new table
`conclusion_requirement_override` (kind 'not_applicable' | 'accept_expired').

Expand-only: a new table nobody in the previous color reads or writes.
Downgrade drops it.
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'r3m4n5o6p7q8'
down_revision = 'q2l3m4n5o6p7'
branch_labels = None
depends_on = None

TABLE = 'conclusion_requirement_override'


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade():
    if TABLE in _tables():
        return
    op.create_table(
        TABLE,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_program_id', sa.Integer(),
                  sa.ForeignKey('user_program.id', ondelete='CASCADE'), nullable=False),
        sa.Column('archive_id', sa.Integer(),
                  sa.ForeignKey('archive.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_program_id', 'archive_id', 'kind',
                            name='uq_conclusion_requirement_override'),
        sa.CheckConstraint("kind IN ('not_applicable', 'accept_expired')",
                           name='ck_conclusion_requirement_override_kind'),
    )
    op.create_index('ix_conclusion_requirement_override_user_program_id', TABLE,
                    ['user_program_id'])
    op.create_index('ix_conclusion_requirement_override_archive_id', TABLE, ['archive_id'])


def downgrade():
    if TABLE in _tables():
        op.drop_table(TABLE)

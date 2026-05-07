"""add_academic_period_to_event

Revision ID: 9q7u9v0w1x2y
Revises: 8p6t8u9v0w1x
Create Date: 2026-04-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '9q7u9v0w1x2y'
down_revision = '8p6t8u9v0w1x'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('event', sa.Column('academic_period_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_event_academic_period',
        'event', 'academic_period',
        ['academic_period_id'], ['id'],
        ondelete='SET NULL'
    )
    op.execute("""
        UPDATE event
        SET academic_period_id = ap.id
        FROM academic_period ap
        WHERE event.event_date::date BETWEEN ap.start_date AND ap.end_date
          AND event.academic_period_id IS NULL
          AND event.event_date IS NOT NULL
    """)


def downgrade():
    op.drop_constraint('fk_event_academic_period', 'event', type_='foreignkey')
    op.drop_column('event', 'academic_period_id')

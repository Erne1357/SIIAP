"""add student role

Revision ID: 7e3g6h8i0j1k
Revises: 6d2f5g7h9i0j
Create Date: 2026-03-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e3g6h8i0j1k'
down_revision = '1edfae1ae666'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "INSERT INTO role (name, description) "
        "SELECT 'student', 'Estudiante activo inscrito en un programa' "
        "WHERE NOT EXISTS (SELECT 1 FROM role WHERE name = 'student')"
    )


def downgrade():
    op.execute("DELETE FROM role WHERE name = 'student'")

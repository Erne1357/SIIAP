"""cleanup deprecated fields: user_program.status and submission.period

Revision ID: 1i7k9l0m1n2o
Revises: 0h6j7k8l9m0n
Create Date: 2026-03-18 12:00:00.000000

Cambios:
- DROP user_program.status  (siempre fue 'active'; la fuente de verdad es admission_status)
- DROP submission.period    (string legacy '2024-2025'; reemplazado por academic_period_id FK)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '1i7k9l0m1n2o'
down_revision = '0h6j7k8l9m0n'
branch_labels = None
depends_on = None


def upgrade():
    # Eliminar campo 'status' de user_program.
    # En producción este campo siempre contiene 'active' (valor por defecto).
    # La fuente de verdad del estado del proceso es admission_status.
    op.drop_column('user_program', 'status')

    # Eliminar campo 'period' de submission.
    # Era un string libre (ej: '2024-2025') usado antes de que existiera AcademicPeriod.
    # Reemplazado completamente por submission.academic_period_id (FK).
    op.drop_column('submission', 'period')


def downgrade():
    # Restaurar 'period' en submission (nullable para no romper registros existentes)
    op.add_column('submission',
        sa.Column('period', sa.String(length=50), nullable=True)
    )

    # Restaurar 'status' en user_program con el valor por defecto original
    op.add_column('user_program',
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active')
    )

"""add period foreign keys and migrate existing data

Revision ID: 4b0d3e5f7h8i
Revises: 3a9c2d4e5f6g
Create Date: 2026-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '4b0d3e5f7h8i'
down_revision = '3a9c2d4e5f6g'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Agregar columna academic_period_id a submission
    op.add_column('submission',
        sa.Column('academic_period_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_submission_academic_period',
        'submission', 'academic_period',
        ['academic_period_id'], ['id'],
        ondelete='SET NULL'
    )

    # 2. Agregar columna admission_period_id a user_program
    op.add_column('user_program',
        sa.Column('admission_period_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_user_program_admission_period',
        'user_program', 'academic_period',
        ['admission_period_id'], ['id'],
        ondelete='SET NULL'
    )

    # 3. Insertar periodo inicial 20253 si no existe
    # Usamos una conexion para verificar y luego insertar
    conn = op.get_bind()

    # Verificar si ya existe el periodo
    result = conn.execute(
        sa.text("SELECT id FROM academic_period WHERE code = '20253'")
    ).fetchone()

    if not result:
        # Insertar periodo inicial
        conn.execute(
            sa.text("""
                INSERT INTO academic_period
                (code, name, start_date, end_date, admission_start_date, admission_end_date, is_active, status, created_at)
                VALUES
                ('20253', 'Agosto-Diciembre 2025', '2025-08-01', '2025-12-15', '2025-05-01', '2025-07-31', true, 'active', :created_at)
            """),
            {'created_at': datetime.utcnow()}
        )

    # 4. Migrar submissions existentes al periodo 20253
    conn.execute(
        sa.text("""
            UPDATE submission
            SET academic_period_id = (SELECT id FROM academic_period WHERE code = '20253')
            WHERE academic_period_id IS NULL
        """)
    )

    # 5. Migrar user_programs existentes al periodo 20253
    conn.execute(
        sa.text("""
            UPDATE user_program
            SET admission_period_id = (SELECT id FROM academic_period WHERE code = '20253')
            WHERE admission_period_id IS NULL
        """)
    )

    # 6. Crear indices para mejorar rendimiento
    op.create_index('ix_submission_academic_period_id', 'submission', ['academic_period_id'])
    op.create_index('ix_user_program_admission_period_id', 'user_program', ['admission_period_id'])


def downgrade():
    # Eliminar indices
    op.drop_index('ix_user_program_admission_period_id', table_name='user_program')
    op.drop_index('ix_submission_academic_period_id', table_name='submission')

    # Eliminar foreign keys
    op.drop_constraint('fk_user_program_admission_period', 'user_program', type_='foreignkey')
    op.drop_constraint('fk_submission_academic_period', 'submission', type_='foreignkey')

    # Eliminar columnas
    op.drop_column('user_program', 'admission_period_id')
    op.drop_column('submission', 'academic_period_id')

    # Nota: No eliminamos el periodo 20253 para preservar datos

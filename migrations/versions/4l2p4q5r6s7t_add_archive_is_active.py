"""add archive.is_active and fix permanence archives

Revision ID: 4l2p4q5r6s7t
Revises: 3k0n2o3p4q5r
Create Date: 2026-03-24 00:00:00.000000

Cambios:
1. Agrega columna is_active a la tabla archive (default TRUE).
2. Desactiva los 4 archives de permanencia que ya no se solicitan:
   - Mapa Curricular (step 9)
   - Programación de Materias (step 9)
   - Boleta de Inscripción (step 9)
   - Boleta de Calificación Firmada/Sellada (step 9)
3. Corrige is_uploadable=TRUE para el Reporte de Retroalimentación (step 9),
   que estaba en FALSE por error.
"""
from alembic import op
import sqlalchemy as sa

revision = '4l2p4q5r6s7t'
down_revision = '3k0n2o3p4q5r'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Agregar columna is_active
    op.add_column(
        'archive',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true')
    )

    # 2. Desactivar los 4 archives obsoletos de permanencia (step_id=9)
    op.execute("""
        UPDATE archive
        SET is_active = FALSE
        WHERE step_id = 9
          AND name IN (
            'Mapa Curricular',
            'Programación de Materias',
            'Boleta de Inscripción',
            'Boleta de Calificación Firmada/Sellada'
          )
    """)

    # 3. Corregir is_uploadable del Reporte de Retroalimentación
    op.execute("""
        UPDATE archive
        SET is_uploadable = TRUE
        WHERE step_id = 9
          AND name = 'Reporte de Retroalimentación'
    """)


def downgrade():
    # Revertir la corrección de is_uploadable
    op.execute("""
        UPDATE archive
        SET is_uploadable = FALSE
        WHERE step_id = 9
          AND name = 'Reporte de Retroalimentación'
    """)

    # Reactivar los archives desactivados
    op.execute("""
        UPDATE archive
        SET is_active = TRUE
        WHERE step_id = 9
          AND name IN (
            'Mapa Curricular',
            'Programación de Materias',
            'Boleta de Inscripción',
            'Boleta de Calificación Firmada/Sellada'
          )
    """)

    # Eliminar la columna
    op.drop_column('archive', 'is_active')

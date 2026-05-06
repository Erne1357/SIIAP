"""schedule_path_in_se_and_optional_submission_file

Cambios:
  1. SemesterEnrollment gana columna `schedule_path` (string nullable). El
     coordinador puede subir el horario del semestre cuando confirma la
     inscripción del estudiante.
  2. Submission.file_path pasa a NULLABLE. Permite que el coordinador apruebe
     o rechace ciertos archivos (ej: exámenes presenciales) sin necesidad de
     subir un PDF — sólo deja el comentario y la decisión.

Revision ID: i4d5e6f7g8h9
Revises: h3c4d5e6f7g8
Create Date: 2026-05-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'i4d5e6f7g8h9'
down_revision = 'h3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('semester_enrollment', sa.Column(
        'schedule_path', sa.String(length=255), nullable=True,
    ))
    op.alter_column(
        'submission', 'file_path',
        existing_type=sa.String(length=200),
        nullable=True,
    )


def downgrade():
    # Convertir NULLs a placeholder antes de restaurar NOT NULL
    op.execute(
        "UPDATE submission SET file_path = '__no_file__' WHERE file_path IS NULL"
    )
    op.alter_column(
        'submission', 'file_path',
        existing_type=sa.String(length=200),
        nullable=False,
    )
    op.drop_column('semester_enrollment', 'schedule_path')

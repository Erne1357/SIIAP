"""add deliberation fields to user_program

Revision ID: 5c1e4f6g8h9j
Revises: 4b0d3e5f7h8i
Create Date: 2026-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c1e4f6g8h9j'
down_revision = '4b0d3e5f7h8i'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar campos de deliberacion a user_program
    op.add_column('user_program',
        sa.Column('admission_status', sa.String(30), nullable=False, server_default='in_progress')
    )
    op.add_column('user_program',
        sa.Column('deliberation_started_at', sa.DateTime(), nullable=True)
    )
    op.add_column('user_program',
        sa.Column('decision_at', sa.DateTime(), nullable=True)
    )
    op.add_column('user_program',
        sa.Column('decision_by', sa.Integer(), nullable=True)
    )
    op.add_column('user_program',
        sa.Column('decision_notes', sa.Text(), nullable=True)
    )
    op.add_column('user_program',
        sa.Column('rejection_type', sa.String(30), nullable=True)
    )
    op.add_column('user_program',
        sa.Column('correction_required', sa.Text(), nullable=True)
    )

    # Crear foreign key para decision_by
    op.create_foreign_key(
        'fk_user_program_decision_by',
        'user_program', 'user',
        ['decision_by'], ['id'],
        ondelete='SET NULL'
    )

    # Crear indice para mejorar consultas por admission_status
    op.create_index('ix_user_program_admission_status', 'user_program', ['admission_status'])


def downgrade():
    # Eliminar indice
    op.drop_index('ix_user_program_admission_status', table_name='user_program')

    # Eliminar foreign key
    op.drop_constraint('fk_user_program_decision_by', 'user_program', type_='foreignkey')

    # Eliminar columnas
    op.drop_column('user_program', 'correction_required')
    op.drop_column('user_program', 'rejection_type')
    op.drop_column('user_program', 'decision_notes')
    op.drop_column('user_program', 'decision_by')
    op.drop_column('user_program', 'decision_at')
    op.drop_column('user_program', 'deliberation_started_at')
    op.drop_column('user_program', 'admission_status')

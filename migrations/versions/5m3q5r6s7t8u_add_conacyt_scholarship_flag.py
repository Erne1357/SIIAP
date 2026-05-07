"""add user_program.has_conacyt_scholarship

Revision ID: 5m3q5r6s7t8u
Revises: 4l2p4q5r6s7t
Create Date: 2026-03-24 00:00:00.000000

Agrega el campo has_conacyt_scholarship a user_program.
Permite al coordinador marcar si un estudiante es becario CONACyT activo,
lo que activa la visualización y entrega del Formato de Desempeño mensual
(Módulo C — Permanencia Semestral).
"""
from alembic import op
import sqlalchemy as sa

revision = '5m3q5r6s7t8u'
down_revision = '4l2p4q5r6s7t'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'user_program',
        sa.Column(
            'has_conacyt_scholarship',
            sa.Boolean(),
            nullable=False,
            server_default='false'
        )
    )


def downgrade():
    op.drop_column('user_program', 'has_conacyt_scholarship')

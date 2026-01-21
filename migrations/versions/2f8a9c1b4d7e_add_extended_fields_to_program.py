"""add extended fields to program

Revision ID: 2f8a9c1b4d7e
Revises: ef9bdf6fabb7
Create Date: 2025-12-03 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import os


# revision identifiers, used by Alembic.
revision = '2f8a9c1b4d7e'
down_revision = 'ef9bdf6fabb7'
branch_labels = None
depends_on = None


def upgrade():
    # === Agregar columnas nuevas a la tabla program ===

    # 1. INFORMACIÓN GENERAL EXTENDIDA
    op.add_column('program', sa.Column('program_level', sa.String(50), nullable=True))
    op.add_column('program', sa.Column('academic_area', sa.String(100), nullable=True))
    op.add_column('program', sa.Column('image_filename', sa.String(255), nullable=True))
    op.add_column('program', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

    # 2. DURACIÓN Y MODALIDAD
    op.add_column('program', sa.Column('duration_semesters', sa.Integer(), nullable=True))
    op.add_column('program', sa.Column('duration_years', sa.Numeric(3, 1), nullable=True))
    op.add_column('program', sa.Column('modality', sa.String(50), nullable=True))
    op.add_column('program', sa.Column('schedule_info', sa.Text(), nullable=True))

    # 3. INFORMACIÓN ACADÉMICA
    op.add_column('program', sa.Column('introduction_text', sa.Text(), nullable=True))
    op.add_column('program', sa.Column('recognition_text', sa.Text(), nullable=True))
    op.add_column('program', sa.Column('scholarship_info', sa.Text(), nullable=True))
    op.add_column('program', sa.Column('admission_requirements', sa.Text(), nullable=True))

    # 4. OBJETIVOS (JSON)
    op.add_column('program', sa.Column('objectives', sa.JSON(), nullable=True))

    # 5. PERFIL DEL EGRESADO (JSON)
    op.add_column('program', sa.Column('graduate_profile_intro', sa.Text(), nullable=True))
    op.add_column('program', sa.Column('graduate_competencies', sa.JSON(), nullable=True))

    # 6. LÍNEAS DE INVESTIGACIÓN (JSON)
    op.add_column('program', sa.Column('research_lines', sa.JSON(), nullable=True))

    # 7. MAPA CURRICULAR (JSON)
    op.add_column('program', sa.Column('curriculum_structure', sa.JSON(), nullable=True))
    op.add_column('program', sa.Column('show_curriculum', sa.Boolean(), nullable=False, server_default='true'))

    # 8. INFORMACIÓN DE CONTACTO
    op.add_column('program', sa.Column('contact_email', sa.String(255), nullable=True))
    op.add_column('program', sa.Column('contact_email_secondary', sa.String(255), nullable=True))
    op.add_column('program', sa.Column('contact_phone', sa.String(50), nullable=True))
    op.add_column('program', sa.Column('contact_phone_secondary', sa.String(50), nullable=True))
    op.add_column('program', sa.Column('contact_address', sa.Text(), nullable=True))
    op.add_column('program', sa.Column('contact_office', sa.String(100), nullable=True))
    op.add_column('program', sa.Column('contact_hours', sa.String(255), nullable=True))

    # 9. CONFIGURACIÓN DE VISUALIZACIÓN
    op.add_column('program', sa.Column('show_hero_cards', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('program', sa.Column('show_objectives', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('program', sa.Column('show_graduate_profile', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('program', sa.Column('show_research_lines', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('program', sa.Column('show_contact_section', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('program', sa.Column('show_contact_form', sa.Boolean(), nullable=False, server_default='true'))

    # 10. SEO Y METADATOS
    op.add_column('program', sa.Column('meta_title', sa.String(255), nullable=True))
    op.add_column('program', sa.Column('meta_description', sa.Text(), nullable=True))
    op.add_column('program', sa.Column('meta_keywords', sa.String(255), nullable=True))

    # === Ejecutar script SQL con los datos ===
    # Leer y ejecutar el script de datos
    script_path = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'DML', '07_update_program_extended_fields.sql')

    if os.path.exists(script_path):
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
            # Dividir por UPDATE y filtrar solo las partes válidas (que empiezan con SET)
            statements = sql_script.split('UPDATE program')
            for statement in statements:
                statement = statement.strip()
                # Solo ejecutar si el statement empieza con SET (excluye comentarios)
                if statement and statement.startswith('SET'):
                    op.execute('UPDATE program ' + statement)
    else:
        print(f"Warning: SQL script not found at {script_path}")


def downgrade():
    # === Remover columnas en orden inverso ===

    # SEO
    op.drop_column('program', 'meta_keywords')
    op.drop_column('program', 'meta_description')
    op.drop_column('program', 'meta_title')

    # Configuración de visualización
    op.drop_column('program', 'show_contact_form')
    op.drop_column('program', 'show_contact_section')
    op.drop_column('program', 'show_research_lines')
    op.drop_column('program', 'show_graduate_profile')
    op.drop_column('program', 'show_objectives')
    op.drop_column('program', 'show_hero_cards')

    # Contacto
    op.drop_column('program', 'contact_hours')
    op.drop_column('program', 'contact_office')
    op.drop_column('program', 'contact_address')
    op.drop_column('program', 'contact_phone_secondary')
    op.drop_column('program', 'contact_phone')
    op.drop_column('program', 'contact_email_secondary')
    op.drop_column('program', 'contact_email')

    # Mapa curricular
    op.drop_column('program', 'show_curriculum')
    op.drop_column('program', 'curriculum_structure')

    # Líneas de investigación
    op.drop_column('program', 'research_lines')

    # Perfil del egresado
    op.drop_column('program', 'graduate_competencies')
    op.drop_column('program', 'graduate_profile_intro')

    # Objetivos
    op.drop_column('program', 'objectives')

    # Información académica
    op.drop_column('program', 'admission_requirements')
    op.drop_column('program', 'scholarship_info')
    op.drop_column('program', 'recognition_text')
    op.drop_column('program', 'introduction_text')

    # Duración y modalidad
    op.drop_column('program', 'schedule_info')
    op.drop_column('program', 'modality')
    op.drop_column('program', 'duration_years')
    op.drop_column('program', 'duration_semesters')

    # Información general
    op.drop_column('program', 'is_active')
    op.drop_column('program', 'image_filename')
    op.drop_column('program', 'academic_area')
    op.drop_column('program', 'program_level')

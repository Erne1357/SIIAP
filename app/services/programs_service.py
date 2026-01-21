# app/services/programs_service.py
from sqlalchemy.orm import joinedload, selectinload
from app import db
from app.models.program import Program
from app.models.step import Step
from app.models.program_step import ProgramStep
from app.models.user_program import UserProgram

class AlreadyEnrolledError(Exception): ...
class ProgramNotFound(Exception): ...

def list_programs():
    return Program.query.order_by(Program.name).all()

def get_program_by_slug(slug: str):
    program = (Program.query.filter_by(slug=slug)
        .options(
            joinedload(Program.program_steps)
              .joinedload(ProgramStep.step)
              .joinedload(Step.phase),
            joinedload(Program.program_steps)
              .joinedload(ProgramStep.step)
              .selectinload(Step.archives)
        )
        .first())
    if not program:
        raise ProgramNotFound()
    return program

def enroll_user_once(program_id: int, user_id: int):
    program = Program.query.get(program_id)
    if not program:
        raise ProgramNotFound()

    already = UserProgram.query.filter_by(user_id=user_id).first()
    if already:
        raise AlreadyEnrolledError("Ya estás inscrito en un programa.")

    db.session.add(UserProgram(user_id=user_id, program_id=program.id))
    db.session.commit()
    return program


def update_program_config(program_id: int, data: dict):
    """
    Actualiza la configuración extendida de un programa.

    Args:
        program_id: ID del programa
        data: Diccionario con los campos a actualizar

    Returns:
        Program: Programa actualizado
    """
    program = Program.query.get(program_id)
    if not program:
        raise ProgramNotFound()

    # Lista de campos permitidos para actualizar
    allowed_fields = [
        # Información general
        'program_level', 'academic_area', 'image_filename', 'is_active',
        # Duración y modalidad
        'duration_semesters', 'duration_years', 'modality', 'schedule_info',
        # Información académica
        'introduction_text', 'recognition_text', 'scholarship_info', 'admission_requirements',
        # Objetivos y perfil (JSON)
        'objectives', 'graduate_profile_intro', 'graduate_competencies',
        # Líneas de investigación (JSON)
        'research_lines',
        # Mapa curricular (JSON)
        'curriculum_structure', 'show_curriculum',
        # Contacto
        'contact_email', 'contact_email_secondary', 'contact_phone', 'contact_phone_secondary',
        'contact_address', 'contact_office', 'contact_hours',
        # Configuración de visualización
        'show_hero_cards', 'show_objectives', 'show_graduate_profile',
        'show_research_lines', 'show_contact_section', 'show_contact_form',
        # SEO
        'meta_title', 'meta_description', 'meta_keywords'
    ]

    # Actualizar solo los campos permitidos que vengan en data
    for field in allowed_fields:
        if field in data:
            setattr(program, field, data[field])

    db.session.commit()
    return program

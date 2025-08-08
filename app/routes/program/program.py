from flask import Blueprint, render_template,redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload, selectinload
from app import db
from app.models.program import Program  
from app.models.step import Step  
from app.models.program_step import ProgramStep  
from app.models.user_program import UserProgram
from app.utils.auth import roles_required
from app.routes.program.admission import admission_bp
import logging

program_bp = Blueprint('program', __name__, url_prefix='/programs')
program_bp.register_blueprint(admission_bp)

@program_bp.route('/', methods=['GET'])
@login_required
def list_programs():
    """
    Lista todos los programas disponibles.
    """
    programs = Program.query.all()
    return render_template('programs/list.html', programs=programs)

@program_bp.route('/<string:slug>', methods=['GET'])
@login_required
def view_program(slug):
    """
    Muestra los detalles de un programa específico.
    """
    program = (
    Program.query
    .filter_by(slug=slug)
    .options(
        # 1) Program → ProgramStep → Step → Phase
        joinedload(Program.program_steps)
          .joinedload(ProgramStep.step)
          .joinedload(Step.phase),

        # 2) Program → ProgramStep → Step → Archives
        joinedload(Program.program_steps)
          .joinedload(ProgramStep.step)
          .selectinload(Step.archives)
    )
    .first_or_404()
    )
    if not program:
        return render_template('404.html'), 404
    return render_template('programs/view/view.html', program=program)

@program_bp.route('/<int:program_id>/inscription', methods=['POST'])
@login_required
@roles_required('applicant')                    # ② protección declarativa
def inscription_program(program_id):
    """Registra al usuario en UN (1) programa."""
    program = Program.query.get_or_404(program_id)

    # ③ ¿Ya está inscrito en algún programa?
    already = UserProgram.query.filter_by(user_id=current_user.id).first()
    if already:
        flash('Ya estás inscrito en un programa. No puedes inscribirte a otro.', 'warning')
        return redirect(url_for('program.view_program', slug=program.slug))

    # ④ Crear la inscripción
    db.session.add(UserProgram(user_id=current_user.id, program_id=program.id))
    db.session.commit()
    flash('Te has inscrito en el programa.', 'success')
    return redirect(url_for('program.admission.admission_dashboard', slug=program.slug))

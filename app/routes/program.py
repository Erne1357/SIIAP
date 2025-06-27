from flask import Blueprint, render_template,redirect, url_for, flash
from flask_login import login_required, current_user
from flask_security import roles_required
from sqlalchemy.orm import joinedload, selectinload
from app import db
from app.models.program import Program  
from app.models.step import Step  
from app.models.program_step import ProgramStep  
from app.models.user_program import UserProgram

program_bp = Blueprint('program', __name__, url_prefix='/programs')


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

@program_bp.route('/programs/<program_id>/inscription', methods=['POST'])
@login_required
@roles_required('applicant')
def inscription_program(program_id):
    """
    Registra a un usuario en un programa específico.
    """
    program = Program.query.get_or_404(program_id)
    user_id = current_user.id
    user_program = UserProgram.query.filter_by(user_id=user_id, program_id=program.id).first()
    if user_program:
        flash('Ya estás inscrito en un programa.', 'warning')
        return redirect(url_for('program.view_program', slug=program.slug))

    user_program = UserProgram(user_id=user_id, program_id=program.id)
    db.session.add(user_program)
    db.session.commit()
    flash('Te has inscrito en el programa.', 'success')

    return redirect(url_for('program.view_program', slug=program.slug))

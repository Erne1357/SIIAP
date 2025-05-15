from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy.orm import joinedload, selectinload
from app import db
from app.models.program import Program  
from app.models.step import Step  
from app.models.program_step import ProgramStep  

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
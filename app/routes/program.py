from flask import Blueprint, render_template
from flask_login import login_required
from app.models.program import Program  # Ajusta el import según tu estructura real

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
    program = Program.query.filter_by(slug=slug).first_or_404()
    if not program:
        return render_template('404.html'), 404
    return render_template('programs/view.html', program=program)
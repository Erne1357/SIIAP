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

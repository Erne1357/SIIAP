# app/routes/pages/admission_pages.py
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Program, UserProgram
from app.services.admission_service import get_admission_state

admission_bp = Blueprint('admission', __name__, url_prefix='/admission')

@admission_bp.route('/<string:slug>', methods=['GET'])
@login_required
def admission_dashboard(slug):
    # validar inscripción
    program = Program.query.filter_by(slug=slug).first_or_404()
    up = UserProgram.query.filter_by(program_id=program.id, user_id=current_user.id).first()
    if not up:
        flash('Debes inscribirte antes de subir documentos.', 'warning')
        return redirect(url_for('program.view_program', slug=slug))

    # Para GET, delega al servicio (como antes)
    context = get_admission_state(current_user.id, program.id, up)
    return render_template('programs/admission/admission_dashboard.html', program=program, **context)

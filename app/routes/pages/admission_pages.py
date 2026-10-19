# app/routes/pages/admission_pages.py
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.services import programs_service
from app.services.admission_service import get_admission_state
from app.utils.permissions import permission_required

admission_bp = Blueprint('admission', __name__, url_prefix='/admission')

@admission_bp.route('/<string:slug>', methods=['GET'])
@login_required
@permission_required('submissions.api.upload')
def admission_dashboard(slug):
    # validar inscripción
    program = programs_service.find_program_by_slug(slug)
    if program is None:
        abort(404)
    up = programs_service.find_user_program(current_user.id, program.id)
    if not up:
        flash('Debes inscribirte antes de subir documentos.', 'warning')
        return redirect(url_for('program.view_program', slug=slug))

    # Para GET, delega al servicio (como antes)
    context = get_admission_state(current_user.id, program.id, up)
    return render_template('programs/admission/admission_dashboard.html', program=program, **context)

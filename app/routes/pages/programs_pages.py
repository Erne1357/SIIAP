# app/routes/pages/programs_pages.py
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services import programs_service as svc
from app.routes.pages.admission_pages import admission_bp

program_bp = Blueprint('program', __name__, url_prefix='/programs')
program_bp.register_blueprint(admission_bp)

@program_bp.route('/', methods=['GET'])
@login_required
def list_programs():
    programs = svc.list_programs()
    return render_template('programs/list.html', programs=programs)

@program_bp.route('/<string:slug>', methods=['GET'])
@login_required
def view_program(slug):
    try:
        program = svc.get_program_by_slug(slug)
    except Exception:
        return render_template('404.html'), 404
    return render_template('programs/view/view.html', program=program)

@program_bp.route('/<int:program_id>/inscription', methods=['POST'])
@login_required
@roles_required('applicant')
def inscription_program(program_id):
    # SSR: mantiene flash + redirect sin JS
    try:
        program = svc.enroll_user_once(program_id, current_user.id)
        flash('Te has postulado en el programa.', 'success')
        return redirect(url_for('program.admission.admission_dashboard', slug=program.slug))
    except svc.AlreadyEnrolledError as e:
        # Si ya está inscrito, redirige al detalle del programa que intentó ver
        p = None
        try:
            # intenta obtener slug para no romper la UX
            p = svc.get_program_by_slug(program_id)  # podría no aplicar si program_id != slug
        except Exception:
            pass
        flash(str(e), 'warning')
        if p:
            return redirect(url_for('program.view_program', slug=p.slug))
        return redirect(url_for('program.list_programs'))

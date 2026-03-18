# app/routes/pages/programs_pages.py
from flask import Blueprint, render_template, redirect, url_for, flash, abort
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

    open_period = svc.get_open_admission_period()
    admission_open = open_period is not None
    next_period = svc.get_next_upcoming_period() if not admission_open else None

    return render_template(
        'programs/view/view.html',
        program=program,
        admission_open=admission_open,
        next_period=next_period,
    )

@program_bp.route('/<int:program_id>/inscription', methods=['POST'])
@login_required
@roles_required('applicant')
def inscription_program(program_id):
    # SSR: mantiene flash + redirect sin JS
    try:
        program = svc.enroll_user_once(program_id, current_user.id)
        flash('Te has postulado en el programa.', 'success')
        return redirect(url_for('program.admission.admission_dashboard', slug=program.slug))
    except svc.AdmissionClosedError:
        flash('Las inscripciones están cerradas en este momento.', 'warning')
        from app.models.program import Program
        prog = Program.query.get(program_id)
        if prog:
            return redirect(url_for('program.view_program', slug=prog.slug))
        return redirect(url_for('program.list_programs'))
    except svc.AlreadyEnrolledError as e:
        flash(str(e), 'warning')
        from app.models.program import Program
        prog = Program.query.get(program_id)
        if prog:
            return redirect(url_for('program.view_program', slug=prog.slug))
        return redirect(url_for('program.list_programs'))

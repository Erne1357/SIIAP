# app/routes/pages/coordinator_pages.py
from flask import Blueprint, render_template, current_app
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.models.program import Program
import logging

pages_coordinator = Blueprint('pages_coordinator', __name__, url_prefix='/coordinator')

@pages_coordinator.route('/dashboard')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def dashboard():
    """Dashboard principal del coordinador"""
    # Obtener programas que puede gestionar
    if current_user.role.name == 'program_admin':
        coordinator_programs = Program.query.filter_by(coordinator_id=current_user.id).all()
        current_app.logger.warning(f"Coordinator {current_user.id} manages programs: {[p.id for p in coordinator_programs]}")
    else:
        # Admin puede ver todos
        current_app.logger.warning(f"Admin {current_user.id} accessing all programs")
        coordinator_programs = Program.query.all()
    
    return render_template('coordinator/dashboard.html',
                         coordinator_programs=coordinator_programs)


@pages_coordinator.route('/deliberation')
@pages_coordinator.route('/deliberation/<int:program_id>')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def deliberation(program_id=None):
    """Vista de deliberación de aspirantes"""
    # Obtener programas que puede gestionar
    if current_user.role.name == 'program_admin':
        coordinator_programs = Program.query.filter_by(coordinator_id=current_user.id).all()
    else:
        coordinator_programs = Program.query.all()

    # Si se especifica un programa, validar que el usuario tenga acceso
    selected_program = None
    if program_id:
        selected_program = Program.query.get_or_404(program_id)
        if current_user.role.name == 'program_admin' and selected_program.coordinator_id != current_user.id:
            from flask import abort
            abort(403)
    elif coordinator_programs:
        selected_program = coordinator_programs[0]

    return render_template('coordinator/deliberation.html',
                         coordinator_programs=coordinator_programs,
                         selected_program=selected_program)


@pages_coordinator.route('/acceptance')
@pages_coordinator.route('/acceptance/<int:program_id>')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def acceptance(program_id=None):
    """Vista de documentos de aceptacion e inscripcion."""
    if current_user.role.name == 'program_admin':
        coordinator_programs = Program.query.filter_by(coordinator_id=current_user.id).all()
    else:
        coordinator_programs = Program.query.all()

    selected_program = None
    if program_id:
        selected_program = Program.query.get_or_404(program_id)
        if current_user.role.name == 'program_admin' and selected_program.coordinator_id != current_user.id:
            from flask import abort
            abort(403)
    elif coordinator_programs:
        selected_program = coordinator_programs[0]

    return render_template('coordinator/acceptance.html',
                           coordinator_programs=coordinator_programs,
                           selected_program=selected_program)


@pages_coordinator.route('/permanence')
@pages_coordinator.route('/permanence/<int:program_id>')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def permanence(program_id=None):
    """Vista de permanencia semestral de estudiantes."""
    from app.models.academic_period import AcademicPeriod
    if current_user.role.name == 'program_admin':
        coordinator_programs = Program.query.filter_by(coordinator_id=current_user.id).all()
    else:
        coordinator_programs = Program.query.all()

    selected_program = None
    if program_id:
        selected_program = Program.query.get_or_404(program_id)
        if current_user.role.name == 'program_admin' and selected_program.coordinator_id != current_user.id:
            from flask import abort
            abort(403)
    elif coordinator_programs:
        selected_program = coordinator_programs[0]

    active_period = AcademicPeriod.get_active_period()
    all_periods = AcademicPeriod.query.order_by(AcademicPeriod.start_date.desc()).all()

    # Archives activos de la fase de permanencia (phase_id=2) para el modal "Nueva Ventana"
    from app.models.archive import Archive
    from app.models.step import Step
    permanence_archives = (
        Archive.query
        .join(Step, Archive.step_id == Step.id)
        .filter(Step.phase_id == 2, Archive.is_active == True)
        .order_by(Step.id, Archive.name)
        .all()
    )

    return render_template('coordinator/permanence.html',
                           coordinator_programs=coordinator_programs,
                           selected_program=selected_program,
                           active_period=active_period,
                           all_periods=all_periods,
                           permanence_archives=permanence_archives)
# app/routes/pages/coordinator_pages.py
from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from app.utils.permissions import permission_required
from app.services import coordinator_service, deliberation_service

pages_coordinator = Blueprint('pages_coordinator', __name__, url_prefix='/coordinator')

def _accessible_programs():
    """Programas visibles para el usuario: coordinados + delegados (o todos si postgrad)."""
    return coordinator_service.accessible_programs(current_user.get_accessible_program_ids())


@pages_coordinator.route('/dashboard')
@login_required
@permission_required('coordinator.page.view')
def dashboard():
    """Dashboard principal del coordinador"""
    coordinator_programs = _accessible_programs()
    return render_template('coordinator/dashboard.html',
                         coordinator_programs=coordinator_programs)


def _programs_payload(programs):
    """Lista mínima [{id, name}] para inyectar como JSON al cliente."""
    return [{'id': p.id, 'name': p.name} for p in programs]


@pages_coordinator.route('/deliberation')
@pages_coordinator.route('/deliberation/<int:program_id>')
@login_required
@permission_required('deliberation.page.view')
def deliberation(program_id=None):
    """Vista de deliberación de aspirantes"""
    coordinator_programs = _accessible_programs()
    accessible_pids = current_user.get_accessible_program_ids()

    selected_program = None
    if program_id:
        selected_program = coordinator_service.get_program_or_404(program_id)
        if accessible_pids is not None and selected_program.id not in accessible_pids:
            abort(403)
    # Default = "Todos los programas" (selected_program=None)

    return render_template('coordinator/deliberation.html',
                         coordinator_programs=coordinator_programs,
                         coordinator_programs_json=_programs_payload(coordinator_programs),
                         selected_program=selected_program,
                         conclusion_requirements=deliberation_service.list_conclusion_requirements(
                             [p.id for p in coordinator_programs]))


@pages_coordinator.route('/acceptance')
@pages_coordinator.route('/acceptance/<int:program_id>')
@login_required
@permission_required('acceptance.page.view')
def acceptance(program_id=None):
    """Vista de documentos de aceptacion e inscripcion."""
    coordinator_programs = _accessible_programs()
    accessible_pids = current_user.get_accessible_program_ids()

    selected_program = None
    if program_id:
        selected_program = coordinator_service.get_program_or_404(program_id)
        if accessible_pids is not None and selected_program.id not in accessible_pids:
            abort(403)
    # Default = "Todos los programas" (selected_program=None)

    return render_template('coordinator/acceptance.html',
                           coordinator_programs=coordinator_programs,
                           coordinator_programs_json=_programs_payload(coordinator_programs),
                           selected_program=selected_program)


@pages_coordinator.route('/permanence')
@pages_coordinator.route('/permanence/<int:program_id>')
@login_required
@permission_required('permanence.page.view')
def permanence(program_id=None):
    """Vista de permanencia semestral de estudiantes."""
    coordinator_programs = _accessible_programs()
    accessible_pids = current_user.get_accessible_program_ids()

    selected_program = None
    if program_id:
        selected_program = coordinator_service.get_program_or_404(program_id)
        if accessible_pids is not None and selected_program.id not in accessible_pids:
            abort(403)
    # Default = "Todos los programas" (selected_program=None)

    ctx = coordinator_service.permanence_page_context()

    return render_template('coordinator/permanence.html',
                           coordinator_programs=coordinator_programs,
                           coordinator_programs_json=_programs_payload(coordinator_programs),
                           selected_program=selected_program,
                           active_period=ctx['active_period'],
                           all_periods=ctx['all_periods'],
                           permanence_archives=ctx['permanence_archives'])
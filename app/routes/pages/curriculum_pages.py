# app/routes/pages/curriculum_pages.py
"""
Page routes for study plans (Configuración → Planes de estudio, phase 6B1).

The page and its HTMX fragments: plan versions of a program and their
subjects. Rules live in `curriculum_service`; every mutation answers with the
refreshed workspace fragment.
"""
from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models.subject import SUBJECT_KINDS
from app.schemas.curriculum import SubjectIn
from app.services import curriculum_service as svc
from app.services import program_scope_service as scope_svc
from app.services.coordinator_service import accessible_programs
from app.services.errors import NotFoundError
from app.utils.htmx import hx_flash, is_htmx, render_fragment
from app.utils.permissions import permission_required
from app.utils.validation import parse_form

pages_curriculum = Blueprint('pages_curriculum', __name__, url_prefix='/curriculum')

_WORKSPACE = 'curriculum/_partials/_workspace.html'
_KIND_LABELS = {
    'required': 'Obligatoria',
    'elective_slot': 'Hueco de optativa',
    'elective': 'Optativa (banco)',
}


def _int_or_404(raw) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        abort(404)


def _program_or_404(program_id):
    """The program when it exists and is in the caller's scope; else the shared 404."""
    program_id = _int_or_404(program_id)
    if not scope_svc.program_in_scope(current_user, program_id):
        abort(404)
    for program in accessible_programs(scope_svc.accessible_program_ids(current_user)):
        if program.id == program_id:
            return program
    abort(404)


def _plan_or_404(plan_id):
    """A plan of a program in scope, or the shared 404 (missing and denied look alike)."""
    try:
        plan = svc.get_plan(plan_id)
    except NotFoundError:
        abort(404)
    _program_or_404(plan.program_id)
    return plan


def _workspace_context(program, plan=None) -> dict:
    """Context of the versions list + subject tables of `plan` (default: the current one)."""
    plans = svc.plans_for_program(program.id)
    if plan is None:
        plan = next((p for p in plans if p.is_current), plans[0] if plans else None)
    subjects = svc.subjects_of(plan.id) if plan is not None else []
    return dict(
        program=program,
        plans=plans,
        plan=plan,
        required_by_semester=_group_required(subjects),
        slots=[s for s in subjects if s.kind == 'elective_slot'],
        bank=[s for s in subjects if s.kind == 'elective'],
        subject_count=len(subjects),
        kind_labels=_KIND_LABELS,
    )


def _workspace(program, plan=None):
    return render_fragment(_WORKSPACE, **_workspace_context(program, plan))


def _group_required(subjects):
    """[(semester or None, [subjects])] of the required subjects, ordered by semester."""
    groups: dict = {}
    for subject in subjects:
        if subject.kind == 'required':
            groups.setdefault(subject.suggested_semester, []).append(subject)
    return sorted(groups.items(), key=lambda item: (item[0] is None, item[0] or 0))


@pages_curriculum.route('/')
@login_required
@permission_required('curriculum.page.manage')
def index():
    """Program selector, plan versions and the subject table of the selected version."""
    programs = accessible_programs(scope_svc.accessible_program_ids(current_user))
    program = None
    if programs:
        raw = (request.args.get('program') or '').strip()
        program = _program_or_404(raw) if raw else programs[0]
    plan = None
    raw_plan = (request.args.get('plan') or '').strip()
    if program is not None and raw_plan:
        plan = _plan_or_404(_int_or_404(raw_plan))
        if plan.program_id != program.id:
            abort(404)
    context = _workspace_context(program, plan) if program else {'program': None}
    return render_template(
        'curriculum/index.html',
        programs=programs,
        kinds=[(kind, _KIND_LABELS[kind]) for kind in SUBJECT_KINDS],
        **context,
    )


@pages_curriculum.route('/plans/<int:plan_id>')
@login_required
@permission_required('curriculum.page.manage')
def plan_fragment(plan_id):
    """Subject tables of one plan version as a fragment."""
    plan = _plan_or_404(plan_id)
    if not is_htmx():
        return redirect(url_for('.index', program=plan.program_id, plan=plan.id))
    return _workspace(plan.program, plan)


@pages_curriculum.route('/plans', methods=['POST'])
@login_required
@permission_required('curriculum.page.manage')
def create_plan():
    """New (not current) version; copies the subjects of `copy_from` or of the current one."""
    program = _program_or_404(request.form.get('program_id'))
    copy_from = (request.form.get('copy_from') or '').strip()
    source_id = None
    if copy_from:
        source_id = _plan_or_404(_int_or_404(copy_from)).id
    plan = svc.create_version(program.id, current_user.id, copy_from_plan_id=source_id)
    return hx_flash(_workspace(program, plan), 'success',
                    f'Versión {plan.version} creada. Aún no es la vigente.')


@pages_curriculum.route('/plans/<int:plan_id>/current', methods=['POST'])
@login_required
@permission_required('curriculum.page.manage')
def set_current(plan_id):
    """Make the version the one new students follow."""
    plan = _plan_or_404(plan_id)
    svc.set_current(plan.id, current_user.id)
    return hx_flash(_workspace(plan.program, plan), 'success',
                    f'La versión {plan.version} es ahora la vigente.')


@pages_curriculum.route('/plans/<int:plan_id>/subjects', methods=['POST'])
@login_required
@permission_required('curriculum.page.manage')
def create_subject(plan_id):
    """Add a subject to the version."""
    plan = _plan_or_404(plan_id)
    svc.save_subject(plan.id, parse_form(SubjectIn), current_user.id)
    return hx_flash(_workspace(plan.program, plan), 'success', 'Materia agregada.')


def _subject_plan_or_404(subject_id):
    try:
        subject = svc.get_subject(subject_id)
    except NotFoundError:
        abort(404)
    return subject, _plan_or_404(subject.plan_id)


@pages_curriculum.route('/subjects/<int:subject_id>', methods=['POST'])
@login_required
@permission_required('curriculum.page.manage')
def edit_subject(subject_id):
    """Edit a subject."""
    subject, plan = _subject_plan_or_404(subject_id)
    svc.save_subject(plan.id, parse_form(SubjectIn), current_user.id, subject_id=subject.id)
    return hx_flash(_workspace(plan.program, plan), 'success', 'Materia actualizada.')


@pages_curriculum.route('/subjects/<int:subject_id>/deactivate', methods=['POST'])
@login_required
@permission_required('curriculum.page.manage')
def deactivate_subject(subject_id):
    """Hide a subject from new groups (existing enrollments keep it)."""
    subject, plan = _subject_plan_or_404(subject_id)
    svc.deactivate_subject(subject.id, current_user.id)
    return hx_flash(_workspace(plan.program, plan), 'success', 'Materia desactivada.')

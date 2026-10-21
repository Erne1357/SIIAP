# app/routes/pages/teaching_pages.py
"""
Page routes for teachers (Docencia → Mis grupos, phase 6B1).

A teacher is whoever a group names as `teacher_id`, whatever their role;
`teaching_scope_service` decides what each user may see.
"""
from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.services import (
    academic_period_service, course_group_service, grading_service,
    teaching_scope_service,
)
from app.services.errors import ValidationFailed
from app.utils.htmx import hx_flash, render_fragment
from app.utils.permissions import permission_required

pages_teaching = Blueprint('pages_teaching', __name__, url_prefix='/teaching')

_ATTEMPT_LABELS = {'ordinary': 'Ordinario', 'repeat': 'Repetición', 'special': 'Especial'}


def _selected_period(periods):
    """The period of `?period=` (an id); the active one, else the newest, by default."""
    raw = (request.args.get('period') or '').strip()
    if raw:
        try:
            wanted = int(raw)
        except ValueError:
            abort(404)
        for period in periods:
            if period.id == wanted:
                return period
        abort(404)
    active = academic_period_service.get_active_period()
    if active is not None:
        return active
    return periods[0] if periods else None


@pages_teaching.route('/')
@login_required
@permission_required('teaching.page.my_groups')
def my_groups():
    """Groups the current user teaches in the selected period."""
    periods = academic_period_service.list_periods_newest_first()
    period = _selected_period(periods)
    groups = (teaching_scope_service.groups_of(current_user.id, period.id)
              if period is not None else [])
    rows = [{'group': g, 'enrolled': course_group_service.enrolled_count(g.id)}
            for g in groups]
    return render_template('teaching/my_groups.html', periods=periods,
                           period=period, rows=rows)


_ACTA_PARTIAL = 'teaching/_partials/_acta.html'


def _viewable_group_or_404(group_uuid):
    """The group, or the shared 404 (unknown and out-of-scope look the same)."""
    group = course_group_service.get_group(group_uuid)
    if group is None or not teaching_scope_service.can_view_group(current_user, group):
        abort(404)
    return group


def _acta_context(group) -> dict:
    """Explicit context of the acta partial for the current viewer."""
    is_teacher = group.teacher_id == current_user.id
    is_open = grading_service.capture_open(group)
    closed = group.status == 'closed'
    return {
        'group': group,
        'rows': grading_service.acta_rows(group.id),
        'is_teacher': is_teacher,
        'editable': (is_teacher and is_open
                     and current_user.has_permission('grades.page.capture')),
        'can_correct': (is_teacher and closed
                        and current_user.has_permission('grades.page.request_correction')),
        'window_text': grading_service.capture_window_text(group),
    }


def _acta_fragment(group, level=None, message=None):
    response = render_fragment(_ACTA_PARTIAL, **_acta_context(group))
    return hx_flash(response, level, message) if message else response


def _grades_from_form() -> dict:
    """`grade-<enrollment_id>` form keys as {enrollment_id: raw value}."""
    grades = {}
    for key, value in request.form.items():
        if key.startswith('grade-'):
            suffix = key[len('grade-'):]
            if not (suffix.isascii() and suffix.isdecimal()):
                raise ValidationFailed('Formulario de calificaciones no válido.')
            grades[int(suffix)] = value
    return grades


@pages_teaching.route('/groups/<uuid:group_uuid>')
@login_required
@permission_required('teaching.page.my_groups')
def group_detail(group_uuid):
    """Acta of a group: the teacher captures it, a manager in scope reads it."""
    group = _viewable_group_or_404(group_uuid)
    return render_template(
        'teaching/group_detail.html',
        enrolled=course_group_service.enrolled_count(group.id),
        **_acta_context(group))


@pages_teaching.route('/groups/<uuid:group_uuid>/grades', methods=['POST'])
@login_required
@permission_required('grades.page.capture')
def save_grades(group_uuid):
    """Save the draft grades of the teacher's own group."""
    group = _viewable_group_or_404(group_uuid)
    grading_service.save_draft(group.id, _grades_from_form(), current_user.id)
    return _acta_fragment(group, 'success', 'Borrador guardado.')


@pages_teaching.route('/groups/<uuid:group_uuid>/close', methods=['POST'])
@login_required
@permission_required('grades.page.capture')
def close_acta(group_uuid):
    """Save any pending input, then close the acta (grades become final)."""
    group = _viewable_group_or_404(group_uuid)
    grades = _grades_from_form()
    if grades:
        grading_service.save_draft(group.id, grades, current_user.id)
    result = grading_service.close_acta(group.id, current_user.id)
    message = f"Acta cerrada: {result['graded']} calificaciones publicadas."
    level = 'success'
    if result['withdrawn']:
        level = 'warning'
        message += (' Baja definitiva automática por reprobar en especial: '
                    + ', '.join(result['withdrawn']) + '.')
    if result.get('to_review'):
        level = 'warning'
        message += (' Reprobaron en especial y la coordinación revisará su caso: '
                    + ', '.join(result['to_review']) + '.')
    return _acta_fragment(group, level, message)


@pages_teaching.route('/groups/<uuid:group_uuid>/corrections', methods=['POST'])
@login_required
@permission_required('grades.page.request_correction')
def request_grade_correction(group_uuid):
    """The teacher asks postgraduate_admin to correct a final grade."""
    group = _viewable_group_or_404(group_uuid)
    try:
        enrollment_id = int((request.form.get('enrollment_id') or '').strip())
    except ValueError:
        raise ValidationFailed('Selecciona la calificación a corregir.')
    grading_service.request_correction(
        enrollment_id, request.form.get('new_value'),
        request.form.get('reason') or '', current_user.id, group_id=group.id)
    return _acta_fragment(group, 'success', 'Solicitud de corrección enviada.')

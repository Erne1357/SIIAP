# app/routes/pages/course_groups_pages.py
"""
Page routes for course groups and academic load (Permanencia → Carga académica,
phase 6B1): groups per period, their roster, and enrolling students.
Rules live in `course_group_service` and `course_enrollment_service`; the read
side lives in `course_load_service`. Every route answers an HTML fragment that
the permanence page swaps into `#courseLoadRoot`.
"""
from flask import Blueprint, abort, request
from flask_login import current_user, login_required

from app.schemas.curriculum import CourseGroupIn, TeacherIn
from app.services import (
    course_enrollment_service, course_group_service, course_load_service,
    program_scope_service, teacher_service,
)
from app.services.errors import ValidationFailed
from app.utils.htmx import hx_flash, render_fragment
from app.utils.permissions import permission_required
from app.utils.validation import parse_form

pages_course_groups = Blueprint('pages_course_groups', __name__, url_prefix='/course-groups')

_PROGRAM_PARTIAL = 'course_groups/_partials/_program.html'
_GROUP_PARTIAL = 'course_groups/_partials/_group.html'
_TEACHER_SELECT_PARTIAL = 'course_groups/_partials/_teacher_select.html'


def _program_or_404(program_id: int):
    """The program, or the shared 404 (unknown and out-of-scope look the same)."""
    program = course_load_service.get_program(program_id)
    if program is None or not program_scope_service.program_in_scope(current_user, program_id):
        abort(404)
    return program


def _group_or_404(group_uuid):
    group = course_group_service.get_group(group_uuid)
    if group is None or not program_scope_service.program_in_scope(
            current_user, group.program_id):
        abort(404)
    return group


def _int_list(name: str) -> list[int]:
    try:
        return [int(v) for v in request.form.getlist(name)]
    except ValueError:
        raise ValidationFailed('La selección no es válida.')


def _program_fragment(program, period_raw, *, summary=None):
    ctx = course_load_service.program_view(program, period_raw)
    ctx['summary'] = summary
    return render_fragment(_PROGRAM_PARTIAL, **ctx)


def _group_fragment(group):
    return render_fragment(_GROUP_PARTIAL, **course_load_service.group_view(group))


@pages_course_groups.route('/program/<int:program_id>')
@login_required
@permission_required('course_groups.page.manage')
def program_groups(program_id):
    """Groups of a program in a period (`?period=`, default the active one)."""
    program = _program_or_404(program_id)
    return _program_fragment(program, request.args.get('period'))


@pages_course_groups.route('/program/<int:program_id>', methods=['POST'])
@login_required
@permission_required('course_groups.page.manage')
def create_group(program_id):
    program = _program_or_404(program_id)
    data = parse_form(CourseGroupIn)
    course_group_service.save_group(program.id, data, current_user.id)
    return hx_flash(_program_fragment(program, data.academic_period_id),
                    'success', 'Grupo creado.')


@pages_course_groups.route('/<uuid:group_uuid>')
@login_required
@permission_required('course_groups.page.manage')
def group_detail(group_uuid):
    return _group_fragment(_group_or_404(group_uuid))


@pages_course_groups.route('/<uuid:group_uuid>', methods=['POST'])
@login_required
@permission_required('course_groups.page.manage')
def edit_group(group_uuid):
    group = _group_or_404(group_uuid)
    data = parse_form(CourseGroupIn)
    course_group_service.save_group(group.program_id, data, current_user.id, group_id=group.id)
    return hx_flash(_group_fragment(group), 'success', 'Grupo actualizado.')


@pages_course_groups.route('/<uuid:group_uuid>/enroll', methods=['POST'])
@login_required
@permission_required('course_groups.page.manage')
def enroll_student(group_uuid):
    group = _group_or_404(group_uuid)
    try:
        user_program_id = int(request.form.get('user_program_id', ''))
    except ValueError:
        raise ValidationFailed('Selecciona un estudiante.')
    slot_raw = (request.form.get('slot_subject_id') or '').strip()
    try:
        slot_id = int(slot_raw) if slot_raw else None
    except ValueError:
        raise ValidationFailed('El hueco de optativa no es válido.')
    course_enrollment_service.enroll(group.id, user_program_id, current_user.id,
                                     slot_subject_id=slot_id)
    return hx_flash(_group_fragment(group), 'success', 'Estudiante inscrito en el grupo.')


@pages_course_groups.route('/<uuid:group_uuid>/drop/<int:enrollment_id>', methods=['POST'])
@login_required
@permission_required('course_groups.page.manage')
def drop_student(group_uuid, enrollment_id):
    group = _group_or_404(group_uuid)
    enrollment = course_load_service.enrollment_of_group(group.id, enrollment_id)
    if enrollment is None:
        abort(404)
    course_enrollment_service.drop(enrollment.id, current_user.id)
    return hx_flash(_group_fragment(group), 'success', 'Estudiante quitado del grupo.')


@pages_course_groups.route('/program/<int:program_id>/enroll-semester', methods=['POST'])
@login_required
@permission_required('course_groups.page.manage')
def enroll_semester(program_id):
    program = _program_or_404(program_id)
    group_ids = course_load_service.groups_of_program(program.id, _int_list('group_ids'))
    student_ids = course_load_service.students_of_program(program.id,
                                                          _int_list('user_program_ids'))
    if not group_ids or not student_ids:
        raise ValidationFailed('Elige al menos un grupo y un estudiante.')
    summary = course_enrollment_service.enroll_semester(group_ids, student_ids, current_user.id)
    period = request.form.get('period')
    return hx_flash(_program_fragment(program, period, summary=summary), 'success',
                    f'Inscripciones realizadas: {summary["enrolled"]}.')


@pages_course_groups.route('/teachers', methods=['POST'])
@login_required
@permission_required('course_groups.page.manage')
@permission_required('teachers.page.create')
def create_teacher():
    """Create (or reuse) a teacher from the group modal; answers the refreshed select."""
    data = parse_form(TeacherIn)
    teacher = teacher_service.create_teacher(
        data.first_name, data.last_name, data.email, current_user.id)
    response = render_fragment(_TEACHER_SELECT_PARTIAL,
                               teachers=teacher_service.teacher_choices(),
                               selected_id=teacher.id)
    return hx_flash(response, 'success',
                    f'Docente listo: {teacher.first_name} {teacher.last_name}.')

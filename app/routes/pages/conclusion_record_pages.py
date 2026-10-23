# app/routes/pages/conclusion_record_pages.py
"""
Coordinator "Conclusión" tab of the student record (phase 6C).

Thesis, tutorial committee and examination board, admission conditions,
conclusion requirements, grade exam and titling revert. Every route renders
the same HTML fragment (HTMX) after calling `conclusion_service`; the student
and program resolution is shared with the other record tabs, and the service
re-checks the program scope (404).
"""
from datetime import date, datetime

from flask import Blueprint, redirect, request, url_for
from flask_login import current_user, login_required

from app.models.thesis import MEMBER_ROLES
from app.models.user import User
from app.routes.pages.student_record_pages import (
    _load_target_or_404, _resolve_trajectory_up,
)
from app.services import academic_status_service as status_svc
from app.services import conclusion_service as svc
from app.services import student_record_service as record_svc
from app.services import teacher_service
from app.services.errors import ValidationFailed
from app.utils.htmx import hx_flash, is_htmx, render_fragment
from app.utils.permissions import permission_required

pages_conclusion_record = Blueprint(
    'pages_conclusion_record',
    __name__,
    url_prefix='/students',
)

_PARTIAL = 'coordinator/student_record/_partials/_conclusion.html'
_BASE = '/<uuid:user_uuid>/record/conclusion'


def _text(name: str) -> str:
    return (request.form.get(name) or '').strip()


def _parse_date(name: str, label: str):
    raw = _text(name)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValidationFailed(f'{label} no es válida.')


def _parse_datetime(name: str, label: str):
    raw = _text(name)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise ValidationFailed(f'{label} no es válida.')


def _int_arg(name: str, label: str) -> int:
    try:
        return int(_text(name))
    except ValueError:
        raise ValidationFailed(f'{label} no es válido.')


def _resolve(user: User, action: str):
    """The student program the request targets (shared 404), scope-checked again by the service."""
    up = _resolve_trajectory_up(user, action)
    return svc.get_user_program(current_user, up.id)


def _fragment(user: User, up=None):
    """Render the Conclusión fragment for `up` (None: the empty state)."""
    ctx = {
        'target_user': user,
        'up': up,
        'program_options': record_svc.trajectory_options(current_user, user),
        'selected_program_id': up.program_id if up is not None else None,
    }
    if up is not None:
        status = svc.effective_status(up)
        exam = svc.current_exam(up)
        read_only = svc.is_read_only(up)
        can_edit_thesis = status in svc.THESIS_STATUSES
        # Each flag mirrors the service refusal, so no form is offered that
        # the service would reject (titled / withdrawn files are read-only).
        ctx.update(
            academic_status=status,
            status_label=status_svc.STATUS_LABELS_ES.get(status, status or '—'),
            thesis=svc.get_thesis(up),
            read_only=read_only,
            can_edit_thesis=can_edit_thesis,
            can_edit_members={'tutorial': can_edit_thesis,
                              'exam': can_edit_thesis and exam is None},
            can_manage_conditions=not read_only,
            can_override=not read_only,
            can_upload_institution=status in svc.INSTITUTION_UPLOAD_STATUSES,
            teachers=teacher_service.teacher_choices(),
            member_roles=MEMBER_ROLES,
            role_labels=svc.ROLE_LABELS_ES,
            body_labels=svc.BODY_LABELS_ES,
            conditions=svc.conditions(up),
            requirement_archives=[a for _, a in svc.conclusion_archives(up.program_id)],
            requirements=svc.requirements(up),
            exam=exam,
            exams=svc.exams(up),
            blockers=svc.exam_blockers(up) if exam is None else [],
            can_revert=(status == status_svc.TITLED
                        and current_user.has_permission('conclusion.page.revert_titled')),
        )
    return render_fragment(_PARTIAL, **ctx)


def _done(user: User, up, message: str):
    return hx_flash(_fragment(user, up), 'success', message)


@pages_conclusion_record.route(_BASE)
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion(user_uuid):
    """Conclusión tab as a fragment."""
    user = _load_target_or_404(user_uuid, 'conclusion')
    if not is_htmx():
        return redirect(url_for('pages_student_record.student_record',
                                user_uuid=user.uuid, tab='conclusion'))
    if not record_svc.trajectory_options(current_user, user):
        return _fragment(user)
    return _fragment(user, _resolve(user, 'conclusion'))


@pages_conclusion_record.route(_BASE + '/thesis', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_thesis(user_uuid):
    """Register the thesis, or edit it when it already exists."""
    user = _load_target_or_404(user_uuid, 'conclusion_thesis')
    up = _resolve(user, 'conclusion_thesis')
    registered_at = _parse_date('registered_at', 'La fecha de registro')
    if svc.get_thesis(up) is None:
        svc.register_thesis(current_user, up.id, _text('title'),
                            _text('research_line') or None, registered_at)
        return _done(user, up, 'Tesis registrada.')
    svc.update_thesis(current_user, up.id, title=_text('title'),
                      research_line=_text('research_line'), registered_at=registered_at)
    return _done(user, up, 'Tesis actualizada.')


@pages_conclusion_record.route(_BASE + '/members', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_member_add(user_uuid):
    """Add an internal or external member to the tutorial committee or the board."""
    user = _load_target_or_404(user_uuid, 'conclusion_member_add')
    up = _resolve(user, 'conclusion_member_add')
    if _text('person') == 'external':
        svc.add_member(current_user, up.id, _text('body'), _text('role'),
                       external_name=_text('external_name'),
                       external_institution=_text('external_institution') or None)
    else:
        svc.add_member(current_user, up.id, _text('body'), _text('role'),
                       user_id=_int_arg('user_id', 'El integrante'))
    return _done(user, up, 'Integrante agregado.')


@pages_conclusion_record.route(_BASE + '/members/<int:member_id>/remove', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_member_remove(user_uuid, member_id):
    """Remove a member of the committee or the board."""
    user = _load_target_or_404(user_uuid, 'conclusion_member_remove')
    up = _resolve(user, 'conclusion_member_remove')
    svc.remove_member(current_user, up.id, member_id)
    return _done(user, up, 'Integrante eliminado.')


@pages_conclusion_record.route(_BASE + '/conditions', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_condition_add(user_uuid):
    """Create an admission condition."""
    user = _load_target_or_404(user_uuid, 'conclusion_condition_add')
    up = _resolve(user, 'conclusion_condition_add')
    svc.create_condition(current_user, up.id, _text('description'),
                         archive_uuid=_text('archive_id') or None,
                         due_date=_parse_date('due_date', 'La fecha límite'))
    return _done(user, up, 'Condición registrada.')


@pages_conclusion_record.route(_BASE + '/conditions/<uuid:condition_uuid>/resolve',
                               methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_condition_resolve(user_uuid, condition_uuid):
    """Mark a condition as met, or waive it (a note is mandatory)."""
    user = _load_target_or_404(user_uuid, 'conclusion_condition_resolve')
    up = _resolve(user, 'conclusion_condition_resolve')
    resolution = _text('resolution')
    svc.resolve_condition(current_user, up.id, condition_uuid, resolution,
                          _text('note') or None)
    return _done(user, up, 'Condición dispensada.' if resolution == 'waived'
                 else 'Condición marcada como cumplida.')


@pages_conclusion_record.route(_BASE + '/requirements/<uuid:archive_uuid>/upload',
                               methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_requirement_upload(user_uuid, archive_uuid):
    """The coordination uploads a document the institution issues."""
    user = _load_target_or_404(user_uuid, 'conclusion_upload')
    up = _resolve(user, 'conclusion_upload')
    svc.upload_institution_document(current_user, up, archive_uuid, request.files.get('file'))
    return _done(user, up, 'Documento cargado.')


@pages_conclusion_record.route(_BASE + '/requirements/<uuid:archive_uuid>/override',
                               methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_requirement_override(user_uuid, archive_uuid):
    """Mark a requirement «no aplica», or accept an expired reused document (reason)."""
    user = _load_target_or_404(user_uuid, 'conclusion_override')
    up = _resolve(user, 'conclusion_override')
    kind = _text('kind')
    svc.set_requirement_override(current_user, up.id, archive_uuid, kind, _text('reason'))
    return _done(user, up, 'Requisito marcado como «no aplica».' if kind == 'not_applicable'
                 else 'Vigencia vencida aceptada.')


@pages_conclusion_record.route(_BASE + '/requirements/<uuid:archive_uuid>/override/remove',
                               methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_requirement_override_remove(user_uuid, archive_uuid):
    """Undo «no aplica» or the acceptance of an expired document."""
    user = _load_target_or_404(user_uuid, 'conclusion_override_remove')
    up = _resolve(user, 'conclusion_override_remove')
    svc.remove_requirement_override(current_user, up.id, archive_uuid, _text('kind'))
    return _done(user, up, 'Decisión retirada.')


@pages_conclusion_record.route(_BASE + '/exam', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_exam_schedule(user_uuid):
    """Schedule the grade exam."""
    user = _load_target_or_404(user_uuid, 'conclusion_exam_schedule')
    up = _resolve(user, 'conclusion_exam_schedule')
    svc.schedule_exam(current_user, up.id,
                      _parse_datetime('scheduled_at', 'La fecha y hora del examen'),
                      _text('place'), _text('notes') or None)
    return _done(user, up, 'Examen de grado agendado.')


@pages_conclusion_record.route(_BASE + '/exam/<uuid:exam_uuid>/result', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_exam_result(user_uuid, exam_uuid):
    """Record the outcome of the scheduled exam."""
    user = _load_target_or_404(user_uuid, 'conclusion_exam_result')
    up = _resolve(user, 'conclusion_exam_result')
    result = _text('result')
    svc.record_exam_result(
        current_user, up.id, exam_uuid, result,
        verdict=_text('verdict') or None,
        honorific_mention=request.form.get('honorific_mention') == '1',
        acta_folio=_text('acta_folio') or None,
        held_on=_parse_date('held_on', 'La fecha del examen'),
        notes=_text('notes') or None)
    return _done(user, up, 'Estudiante titulado.' if result == 'approved'
                 else 'Resultado registrado: examen suspendido.')


@pages_conclusion_record.route(_BASE + '/exam/<uuid:exam_uuid>/cancel', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.manage')
def record_conclusion_exam_cancel(user_uuid, exam_uuid):
    """Cancel the scheduled exam."""
    user = _load_target_or_404(user_uuid, 'conclusion_exam_cancel')
    up = _resolve(user, 'conclusion_exam_cancel')
    svc.cancel_exam(current_user, up.id, exam_uuid, _text('reason') or None)
    return _done(user, up, 'Examen cancelado.')


@pages_conclusion_record.route(_BASE + '/revert-titled', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('conclusion.page.revert_titled')
def record_conclusion_revert_titled(user_uuid):
    """Undo a titling captured by mistake (reason mandatory)."""
    user = _load_target_or_404(user_uuid, 'conclusion_revert_titled')
    up = _resolve(user, 'conclusion_revert_titled')
    svc.revert_titled(current_user, up.id, _text('reason'))
    return _done(user, up, 'Titulación revertida.')

# app/routes/pages/student_record_pages.py
"""
Page routes for the Student Record (Expediente Completo).

Besides the record page itself this blueprint serves the HTML fragments the
record loads lazily (the admission tab, which replaced the dashboard's student
detail modal) and the cross-program summary page: the reduced tier (name,
e-mail, progress) of a student the viewer does not manage.
"""
from datetime import date

from flask import (
    Blueprint, abort, current_app, redirect, render_template, request, url_for,
)
from flask_login import login_required, current_user

from app.models.user import User
from app.services import student_record_service as svc
from app.services import student_admission_detail_service as detail_svc
from app.services import course_enrollment_service, curriculum_service, permanence_service
from app.services.errors import ValidationFailed
from app.utils.htmx import hx_flash, is_htmx, render_fragment
from app.utils.permissions import permission_required

pages_student_record = Blueprint(
    'pages_student_record',
    __name__,
    url_prefix='/students',
)

_ADMISSION_PARTIAL = 'coordinator/student_record/_partials/_admission.html'
_TRAJECTORY_PARTIAL = 'coordinator/student_record/_partials/_trajectory.html'
_LOAD_PARTIAL = 'coordinator/student_record/_partials/_load.html'


def _log_denial(error: svc.StudentRecordError, user_id, action: str) -> None:
    """Record WHICH of the two denials happened. The response never says."""
    reason = 'unknown_user' if isinstance(error, svc.StudentNotFound) else 'out_of_scope'
    current_app.logger.warning(
        "[student_record] %s denied (%s): requester=%s target=%s — %s",
        action, reason, current_user.id, user_id, error,
    )


def _load_target_or_404(user_uuid, action: str) -> User:
    """
    Resolve the record target for the caller or abort with the shared 404.

    404 para las DOS negativas —usuario inexistente y usuario fuera del
    alcance—: el 403 anterior confirmaba qué ids de usuario existen y dejaba
    censar la tabla de cuentas recorriendo /students/1..N. El operador
    conserva la diferencia en el log, no en la respuesta. Un identificador
    desconocido o malformado entra por la MISMA puerta que un usuario fuera del
    alcance: `load_record_target(None, ...)` lanza StudentNotFound.
    """
    target = User.by_uuid(user_uuid)
    user_id = target.id if target else None
    try:
        return svc.load_record_target(user_id, current_user)
    except svc.StudentRecordError as e:
        _log_denial(e, user_id, action)
        abort(404)


@pages_student_record.route('/<uuid:user_uuid>/record')
@login_required
@permission_required('students.page.view_record')
def student_record(user_uuid):
    user = _load_target_or_404(user_uuid, 'page')
    return render_template(
        'coordinator/student_record/index.html',
        target_user=user,
        initial_tab=request.args.get('tab', ''),
    )


@pages_student_record.route('/<uuid:user_uuid>/record/admission')
@login_required
@permission_required('students.page.view_record')
def record_admission(user_uuid):
    """Admission tab (document checklist, metrics, interview) as an HTML fragment."""
    user = _load_target_or_404(user_uuid, 'admission')
    if not is_htmx():
        # Opened directly (copied link): show it inside the full record page.
        return redirect(url_for('.student_record', user_uuid=user.uuid, tab='admision'))
    return render_fragment(
        _ADMISSION_PARTIAL,
        target_user=user,
        **detail_svc.admission_context(current_user, user),
    )


@pages_student_record.route('/<uuid:user_uuid>/record/admission/upload', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('coordinator.api.upload_for_student')
def record_admission_upload(user_uuid):
    """Coordinator uploads (or validates without a file) a document for the student."""
    user = _load_target_or_404(user_uuid, 'admission_upload')
    message = detail_svc.upload_admission_document(
        current_user,
        user,
        archive_uuid=(request.form.get('archive_id') or '').strip(),
        file=request.files.get('file'),
        decision='reject' if request.form.get('decision') == 'reject' else 'approve',
        notes=(request.form.get('notes') or '').strip(),
    )
    response = render_fragment(
        _ADMISSION_PARTIAL,
        target_user=user,
        **detail_svc.admission_context(current_user, user),
    )
    return hx_flash(response, 'success', message)


def _program_arg() -> int | None:
    """`program` from the query string or the form; malformed means no such program."""
    raw = (request.values.get('program') or '').strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        abort(404)


def _resolve_trajectory_up(user: User, action: str):
    """The UserProgram the request targets, or the shared 404."""
    try:
        return svc.trajectory_user_program(current_user, user, _program_arg())
    except svc.StudentRecordError as e:
        _log_denial(e, user.id, action)
        abort(404)


def _trajectory_fragment(user: User, up=None):
    """Render the trajectory fragment for `up` (None: the empty state)."""
    options = svc.trajectory_options(current_user, user)
    trajectory = permanence_service.get_trajectory(up.id) if up is not None else None
    return render_fragment(
        _TRAJECTORY_PARTIAL,
        target_user=user,
        trajectory=trajectory,
        program_options=options,
        selected_program_id=up.program_id if up is not None else None,
    )


@pages_student_record.route('/<uuid:user_uuid>/record/trajectory')
@login_required
@permission_required('students.page.view_record')
def record_trajectory(user_uuid):
    """Trajectory tab (academic status, semesters, withdrawal, graduation) as a fragment."""
    user = _load_target_or_404(user_uuid, 'trajectory')
    if not is_htmx():
        return redirect(url_for('.student_record', user_uuid=user.uuid, tab='trayectoria'))
    if not svc.trajectory_options(current_user, user):
        return _trajectory_fragment(user)
    return _trajectory_fragment(user, _resolve_trajectory_up(user, 'trajectory'))


@pages_student_record.route('/<uuid:user_uuid>/record/trajectory/graduate', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('permanence.api.register_graduation')
def record_trajectory_graduate(user_uuid):
    """Register the student's graduation on the given date."""
    user = _load_target_or_404(user_uuid, 'trajectory_graduate')
    up = _resolve_trajectory_up(user, 'trajectory_graduate')
    raw = (request.form.get('graduated_at') or '').strip()
    try:
        on_date = date.fromisoformat(raw) if raw else None
    except ValueError:
        raise ValidationFailed('La fecha de egreso no es válida.')
    permanence_service.register_graduation(up.id, on_date, current_user.id)
    return hx_flash(_trajectory_fragment(user, up), 'success', 'Egreso registrado.')


@pages_student_record.route('/<uuid:user_uuid>/record/trajectory/withdraw', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('permanence.api.withdraw')
def record_trajectory_withdraw(user_uuid):
    """Definitive withdrawal (baja definitiva) with a mandatory reason."""
    user = _load_target_or_404(user_uuid, 'trajectory_withdraw')
    up = _resolve_trajectory_up(user, 'trajectory_withdraw')
    permanence_service.withdraw(
        up.id, (request.form.get('reason') or '').strip(), current_user.id)
    return hx_flash(_trajectory_fragment(user, up), 'success',
                    'Baja definitiva registrada.')


@pages_student_record.route('/<uuid:user_uuid>/record/trajectory/revert-withdrawal',
                            methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('permanence.api.revert_withdrawal')
def record_trajectory_revert_withdrawal(user_uuid):
    """Undo a definitive withdrawal captured by mistake (reason mandatory)."""
    user = _load_target_or_404(user_uuid, 'trajectory_revert')
    up = _resolve_trajectory_up(user, 'trajectory_revert')
    permanence_service.revert_withdrawal(
        up.id, (request.form.get('reason') or '').strip(), current_user.id)
    return hx_flash(_trajectory_fragment(user, up), 'success',
                    'Baja definitiva revertida.')


def _load_fragment(user: User, up=None):
    """Render the load (Carga) fragment for `up` (None: the empty state)."""
    return render_fragment(
        _LOAD_PARTIAL,
        target_user=user,
        up=up,
        load=course_enrollment_service.load_for(up.id) if up is not None else [],
        plan=up.curriculum_plan if up is not None else None,
        plan_options=curriculum_service.plans_for_program(up.program_id) if up is not None else [],
        can_change_plan=current_user.has_permission('curriculum.page.manage'),
        program_options=svc.trajectory_options(current_user, user),
        selected_program_id=up.program_id if up is not None else None,
    )


@pages_student_record.route('/<uuid:user_uuid>/record/load')
@login_required
@permission_required('students.page.view_record')
def record_load(user_uuid):
    """Load tab (enrolled subjects by period, plan version) as a fragment."""
    user = _load_target_or_404(user_uuid, 'load')
    if not is_htmx():
        return redirect(url_for('.student_record', user_uuid=user.uuid, tab='carga'))
    if not svc.trajectory_options(current_user, user):
        return _load_fragment(user)
    return _load_fragment(user, _resolve_trajectory_up(user, 'load'))


@pages_student_record.route('/<uuid:user_uuid>/record/load/plan', methods=['POST'])
@login_required
@permission_required('students.page.view_record')
@permission_required('curriculum.page.manage')
def record_load_plan(user_uuid):
    """Move the student to another version of the program's study plan (reason required)."""
    user = _load_target_or_404(user_uuid, 'load_plan')
    up = _resolve_trajectory_up(user, 'load_plan')
    try:
        plan_id = int((request.form.get('plan_id') or '').strip())
    except ValueError:
        raise ValidationFailed('Selecciona una versión del plan.')
    curriculum_service.change_student_plan(
        up.id, plan_id, request.form.get('reason') or '', current_user.id)
    return hx_flash(_load_fragment(user, up), 'success',
                    'Versión del plan actualizada.')


@pages_student_record.route('/<uuid:user_uuid>/summary')
@login_required
@permission_required('students.page.view_record')
def student_summary(user_uuid):
    """
    Reduced tier of a student outside the viewer's scope (name, e-mail,
    progress). A student the viewer DOES manage goes to the full record.
    """
    target = User.by_uuid(user_uuid)
    if target is None:
        abort(404)
    try:
        svc.load_record_target(target.id, current_user)
    except svc.StudentRecordError:
        pass
    else:
        return redirect(url_for('.student_record', user_uuid=target.uuid))

    summary = detail_svc.get_cross_program_summary(current_user, target)
    if summary is None:
        current_app.logger.warning(
            "[student_record] summary denied: requester=%s target=%s",
            current_user.id, target.id,
        )
        abort(404)
    return render_template(
        'coordinator/student_record/summary.html',
        summary=summary,
    )

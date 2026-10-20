# app/routes/pages/student_record_pages.py
"""
Page routes for the Student Record (Expediente Completo).

Besides the record page itself this blueprint serves the HTML fragments the
record loads lazily (the admission tab, which replaced the dashboard's student
detail modal) and the cross-program summary page: the reduced tier (name,
e-mail, progress) of a student the viewer does not manage.
"""
from flask import (
    Blueprint, abort, current_app, redirect, render_template, request, url_for,
)
from flask_login import login_required, current_user

from app.models.user import User
from app.services import student_record_service as svc
from app.services import student_admission_detail_service as detail_svc
from app.utils.htmx import hx_flash, is_htmx, render_fragment
from app.utils.permissions import permission_required

pages_student_record = Blueprint(
    'pages_student_record',
    __name__,
    url_prefix='/students',
)

_ADMISSION_PARTIAL = 'coordinator/student_record/_partials/_admission.html'


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

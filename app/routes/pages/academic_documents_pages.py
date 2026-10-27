# app/routes/pages/academic_documents_pages.py
"""
PDF downloads of the academic record (phase 6B3): kardex, report card per
period and group acta. Rules live in `academic_documents_service`.

Unknown and out-of-scope targets answer the same 404.
"""
from io import BytesIO

from flask import Blueprint, abort, current_app, request, send_file
from flask_login import current_user, login_required

from app.models.user import User
from app.services import academic_documents_service as docs
from app.services import course_group_service, teaching_scope_service
from app.services import student_record_service as svc
from app.services.errors import NotFoundError
from app.utils.permissions import permission_required

pages_academic_documents = Blueprint('pages_academic_documents', __name__,
                                     url_prefix='/academic-documents')


def _program_arg():
    raw = request.args.get('program')
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        abort(404)


def _pdf_response(template: str, filename: str, **ctx):
    data = docs.render_pdf(template, **ctx)
    return send_file(BytesIO(data), mimetype='application/pdf', as_attachment=True,
                     download_name=filename)


def _own_up_or_404():
    up = docs.pick_user_program(current_user, _program_arg())
    if up is None:
        abort(404)
    return up


def _record_up_or_404(user_uuid):
    """The target's UserProgram for a viewer in scope, or the shared 404."""
    target = User.by_uuid(user_uuid)
    target_id = target.id if target else None
    try:
        user = svc.load_record_target(target_id, current_user)
        return svc.trajectory_user_program(current_user, user, _program_arg())
    except svc.StudentRecordError as e:
        current_app.logger.warning(
            '[academic_documents] denied: requester=%s target=%s — %s',
            current_user.id, target_id, e)
        abort(404)


def _kardex_response(up):
    ctx = docs.kardex_context(up.id)
    return _pdf_response('pdf/kardex.html',
                         docs.safe_filename('kardex', up.user.control_number) + '.pdf', **ctx)


def _report_card_response(up, period_id):
    try:
        ctx = docs.report_card_context(up.id, period_id)
    except NotFoundError:
        abort(404)
    name = docs.safe_filename('boleta', up.user.control_number, ctx['period'].code) + '.pdf'
    return _pdf_response('pdf/report_card.html', name, **ctx)


@pages_academic_documents.get('/kardex.pdf')
@login_required
@permission_required('kardex.page.export_own_pdf')
def own_kardex_pdf():
    return _kardex_response(_own_up_or_404())


@pages_academic_documents.get('/report-card/<int:period_id>.pdf')
@login_required
@permission_required('kardex.page.export_own_pdf')
def own_report_card_pdf(period_id):
    return _report_card_response(_own_up_or_404(), period_id)


@pages_academic_documents.get('/students/<uuid:user_uuid>/kardex.pdf')
@login_required
@permission_required('kardex.page.export_pdf')
@permission_required('students.page.view_record')
def record_kardex_pdf(user_uuid):
    return _kardex_response(_record_up_or_404(user_uuid))


@pages_academic_documents.get('/students/<uuid:user_uuid>/report-card/<int:period_id>.pdf')
@login_required
@permission_required('kardex.page.export_pdf')
@permission_required('students.page.view_record')
def record_report_card_pdf(user_uuid, period_id):
    return _report_card_response(_record_up_or_404(user_uuid), period_id)


@pages_academic_documents.get('/groups/<uuid:group_uuid>/acta.pdf')
@login_required
@permission_required('grades.page.export_acta')
def acta_pdf(group_uuid):
    group = course_group_service.get_group(group_uuid)
    if group is None or not teaching_scope_service.can_view_group(current_user, group):
        abort(404)
    ctx = docs.acta_context(group.id)                   # DomainError if still open
    name = docs.safe_filename('acta', ctx['subject'].key or ctx['subject'].name,
                              group.group_code, ctx['period'].code) + '.pdf'
    return _pdf_response('pdf/acta.html', name, **ctx)

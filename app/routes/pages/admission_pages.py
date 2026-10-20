# app/routes/pages/admission_pages.py
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.schemas.submissions import UploadSubmissionIn
from app.services import admission_panel_service, programs_service
from app.utils.htmx import hx_flash, is_htmx, render_fragment
from app.utils.permissions import permission_required
from app.utils.validation import parse_form

admission_bp = Blueprint('admission', __name__, url_prefix='/admission')

_UPDATE_TEMPLATE = 'programs/admission/_partials/_panel_update.html'
_REFRESH_TEMPLATE = 'programs/admission/_partials/_panel_refresh.html'


def _pane_response(ctx, level, message):
    """The pane the mutation touched (+ out-of-band tabs / stepper) with its flash.

    The pane the browser must morph depends on the document that changed, so the
    server names it (HX-Retarget) instead of the form hard-coding one.
    """
    active = ctx['active_item']
    resp = render_fragment(_UPDATE_TEMPLATE, **ctx)
    if active is None:
        # The page shows a status banner (no tabs): nothing to swap, just tell.
        resp.headers['HX-Reswap'] = 'none'
    else:
        resp.headers['HX-Retarget'] = '#' + admission_panel_service.pane_dom_id(active)
        resp.headers['HX-Reswap'] = 'morph:outerHTML'
    return hx_flash(resp, level, message)


def _after_plain_post(slug, message):
    """Non-htmx caller (no JS): flash and go back to the screen."""
    flash(message, 'success')
    return redirect(url_for('program.admission.admission_dashboard', slug=slug))


@admission_bp.route('/<string:slug>', methods=['GET'])
@login_required
@permission_required('submissions.api.upload')
def admission_dashboard(slug):
    # validar inscripción
    program = programs_service.find_program_by_slug(slug)
    if program is None:
        abort(404)
    up = programs_service.find_user_program(current_user.id, program.id)
    if not up:
        flash('Debes inscribirte antes de subir documentos.', 'warning')
        return redirect(url_for('program.view_program', slug=slug))

    # Para GET, delega al servicio (como antes)
    context = admission_panel_service.build_panel_context(current_user, program, up)
    return render_template('programs/admission/admission_dashboard.html', **context)


@admission_bp.route('/<string:slug>/panel', methods=['GET'])
@login_required
@permission_required('submissions.api.upload')
def admission_panel(slug):
    """Body of the screen (status banner or document tabs) + the stepper, out of band.

    Target of the real-time refresh (socket event -> hx-get).
    """
    ctx = admission_panel_service.panel_for(
        current_user, slug, active_pane=request.args.get('active'))
    return render_fragment(_REFRESH_TEMPLATE, **ctx)


@admission_bp.route('/<string:slug>/submissions', methods=['POST'])
@login_required
@permission_required('submissions.api.create')
def upload_document(slug):
    """Upload or replace a document; answer with the refreshed pane.

    Same service (and so the same validation: size, extension, scope, step
    locks) as ``POST /api/v1/submissions``.
    """
    form = parse_form(UploadSubmissionIn)
    ctx = admission_panel_service.upload_document(
        current_user, slug, form.archive_id, request.files.get('file'),
        client_locked=request.values.get('locked'))
    message = 'Documento enviado exitosamente.'
    if not is_htmx():
        return _after_plain_post(slug, message)
    return _pane_response(ctx, 'success', message)


@admission_bp.route('/<string:slug>/submissions/<uuid:sub_uuid>', methods=['DELETE'])
@login_required
@permission_required('submissions.api.delete_own')
def delete_submission(slug, sub_uuid):
    """Delete the caller's own document; answer with the refreshed pane."""
    ctx = admission_panel_service.delete_document(
        current_user, slug, sub_uuid, client_locked=request.values.get('locked'))
    return _pane_response(ctx, 'success', 'Archivo eliminado.')

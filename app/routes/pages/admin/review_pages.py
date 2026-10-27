# app/routes/pages/admin/review_pages.py
from flask import Blueprint, abort, render_template, request, redirect, url_for
from flask_login import login_required, current_user

from app.models.submission import Submission
from app.models.user import User
from app.utils.permissions import permission_required, guard_program_scope
from app.services import review_service
from app.services.review_service import SubmissionNotFound
from app.utils.htmx import is_htmx, render_fragment
from app.utils.uuid7 import parse_uuid

pages_review = Blueprint("pages_review", __name__, url_prefix="/review")

VALID_PHASES = set(review_service.VALID_PHASES)


#: Legacy phase filter -> kind of the "Por revisar" inbox.
_PHASE_TO_KIND = {
    'admission': 'admission_doc',
    'permanence': 'permanence_doc',
    'conclusion': 'conclusion_doc',
}


def _inbox_redirect():
    """
    302 to the unified inbox when the viewer holds it (phase 6D); None otherwise
    (social service keeps the legacy list: it has no `review.page.inbox`).
    """
    if not current_user.has_permission('review.page.inbox'):
        return None
    # The inbox cannot filter by one submission or one applicant: a link that
    # carries those filters must not silently lose them. A submission goes to
    # its detail page (which checks scope itself); an applicant filter keeps
    # the legacy list, which honours it.
    submission_handle = request.args.get('submission_id')
    if submission_handle:
        sub_uuid = parse_uuid(submission_handle)
        if sub_uuid is not None:
            return redirect(url_for('pages_admin.pages_review.submission_detail',
                                    sub_uuid=sub_uuid))
        return None
    if request.args.get('applicant_id'):
        return None
    kind = _PHASE_TO_KIND.get((request.args.get('phase') or '').lower())
    program_id = request.args.get('program_id', type=int)
    view = 'decided' if request.args.get('status') in ('approved', 'rejected') else None
    return redirect(url_for('pages_review_inbox.index', kind=kind, program=program_id, view=view))


@pages_review.route("/")
@login_required
@permission_required('admin_review.page.view')
def index():
    return _inbox_redirect() or redirect(url_for("pages_admin.pages_review.submissions"))


@pages_review.route("/submissions")
@login_required
@permission_required('admin_review.page.view')
def submissions():
    """
    Listado de entregas. SIEMPRE acotado a los programas del revisor: sus
    programas coordinados más los delegados. Un documento personal es
    información prohibida entre programas, así que ya no existe el
    interruptor "ver documentos de otros programas".
    """
    moved = _inbox_redirect()
    if moved:
        return moved

    # `applicant_id` llega por query string como UUID público. `type=int` lo
    # habría leído como None en silencio y el listado habría salido SIN filtrar.
    _applicant_raw = request.args.get('applicant_id')
    applicant = User.by_uuid(_applicant_raw)
    applicant_id = applicant.id if applicant else (-1 if _applicant_raw else None)
    program_id   = request.args.get('program_id',   type=int)
    status       = request.args.get('status',       'pending', type=str)
    sort         = request.args.get('sort',         'asc',     type=str)  # FIFO: más antiguos primero
    phase        = (request.args.get('phase') or 'admission').lower()
    if phase not in VALID_PHASES:
        phase = 'admission'

    # Filtrar por un programa concreto sólo es válido dentro del alcance.
    if program_id:
        denied = guard_program_scope(program_id)
        if denied:
            return denied

    submissions_list = review_service.list_submissions_for_review(
        current_user,
        status=status,
        phase=phase,
        applicant_id=applicant_id,
        program_id=program_id,
        sort=sort,
    )

    scoped_programs = review_service.reviewable_programs(current_user)

    context = {
        'submissions': submissions_list,
        'filters': {
            # El filtro vuelve a la plantilla con el identificador PÚBLICO, que
            # es el que el <select> vuelve a enviar.
            'applicant_id': _applicant_raw or None,
            'program_id': program_id,
            'status': status,
            'sort': sort,
            'show_all': False,
            'phase': phase,
        },
        'phase_counts': review_service.pending_counts_by_phase(
            current_user, program_id=program_id
        ),
        'applicants': review_service.reviewable_users(current_user, phase),
        'programs': scoped_programs,
        # La plantilla usa estas dos claves sólo para ofrecer el interruptor
        # "ver otros programas" y para marcar filas de solo-consulta. Ninguno
        # de los dos conceptos existe ya: todo lo que se lista está dentro del
        # alcance y es accionable.
        'is_program_admin': False,
        'managed_program_ids': [p.id for p in scoped_programs],
    }
    # Realtime refresh (siiap:submission:* -> hx-get on this same URL): only the
    # rows plus the out-of-band counters, never the whole page.
    if is_htmx():
        return render_fragment("admin/review/_partials/_submissions_refresh.html", **context)
    return render_fragment("admin/review/submissions_list.html", **context)


@pages_review.route("/submission/<uuid:sub_uuid>")
@login_required
@permission_required('admin_review.page.view')
def submission_detail(sub_uuid):
    """
    Detalle de una entrega. La plantilla expone la URL del archivo, así que
    una entrega de otro programa responde 404 (no 403): el revisor no debe
    saber siquiera que existe.
    """
    row = Submission.by_uuid(sub_uuid)
    try:
        sub = review_service.get_submission_for_review(
            current_user, row.id if row else None, detailed=True
        )
    except SubmissionNotFound:
        abort(404)

    return render_template(
        "admin/review/review_detail.html",
        sub=sub,
        user_program=review_service.user_program_of_submission(sub),
        history=review_service.submission_version_history(current_user, sub),
    )

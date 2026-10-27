# app/routes/pages/review_inbox_pages.py
"""
"Por revisar" inbox (phase 6D): everything the actor may decide, across every
review kind, with the decision made in place.

Routes only parse the request and call `review_inbox_service` /
`review_engine`; scope, permissions and rules live there. Refusals are raised
as `DomainError` subclasses and rendered by the global handler (flash +
`HX-Reswap: none` for an HTMX request).
"""
from datetime import date

from flask import Blueprint, request
from flask_login import current_user, login_required

from app.services import review_engine, review_inbox_service as inbox
from app.services.errors import ValidationFailed
from app.utils.htmx import hx_flash, hx_trigger, render_fragment
from app.utils.permissions import permission_required

pages_review_inbox = Blueprint('pages_review_inbox', __name__, url_prefix='/review')

PAGE = 'review/inbox.html'
ROWS = 'review/_partials/_rows.html'
MODAL = 'review/_partials/_decide_modal.html'

#: Spanish success message per (decision, reverted).
_MESSAGES = {
    ('approve', False): 'Elemento aprobado.',
    ('reject', False): 'Elemento rechazado.',
    ('approve', True): 'Decisión cambiada: elemento aprobado.',
    ('reject', True): 'Decisión cambiada: elemento rechazado.',
}


def _filters(source) -> dict:
    """Filters from query string or form: program (int|None), kind, view, page."""
    return {
        'program': source.get('program', type=int),
        'kind': (source.get('kind') or '').strip() or None,
        'view': source.get('view') or inbox.VIEW_PENDING,
        'page': source.get('page', default=1, type=int),
    }


def _context(filters: dict) -> dict:
    data = inbox.list_items(current_user, program_id=filters['program'], kind=filters['kind'],
                            view=filters['view'], page=filters['page'])
    return {
        'data': data,
        'filters': {'program': filters['program'], 'kind': filters['kind'] or '',
                    'view': data['view'], 'page': data['page']},
        'programs': inbox.program_options(current_user),
        'overdue_days': inbox.OVERDUE_DAYS,
    }


def _text(name: str) -> str:
    return (request.form.get(name) or '').strip()


@pages_review_inbox.route('/')
@login_required
@permission_required('review.page.inbox')
def index():
    return render_fragment(PAGE, **_context(_filters(request.args)))


@pages_review_inbox.route('/rows')
@login_required
@permission_required('review.page.inbox')
def rows():
    return render_fragment(ROWS, **_context(_filters(request.args)))


@pages_review_inbox.route('/<item_kind>/<uuid:item_uuid>/decide')
@login_required
@permission_required('review.page.inbox')
def decide_form(item_kind, item_uuid):
    decision = request.args.get('decision')
    row = inbox.get_row(current_user, item_kind, item_uuid)
    if decision not in ('approve', 'reject'):
        decision = 'approve'
    return render_fragment(MODAL, row=row, decision=decision, filters=_filters(request.args))


def _granted_until():
    raw = _text('granted_until')
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValidationFailed('La fecha límite no es válida.')


@pages_review_inbox.route('/<item_kind>/<uuid:item_uuid>/decide', methods=['POST'])
@login_required
@permission_required('review.page.inbox')
def decide(item_kind, item_uuid):
    decision = _text('decision')
    extra = None
    if item_kind == 'extension' and decision == 'approve':
        extra = {'granted_until': _granted_until(),
                 'condition_text': _text('condition_text') or None}
    result = review_engine.decide(
        current_user, item_kind, item_uuid, decision,
        comment=_text('comment'), revert_reason=_text('revert_reason') or None, extra=extra)
    context = _context(_filters(request.form))
    response = render_fragment(ROWS, **context)
    response = hx_flash(response, 'success', _MESSAGES.get((decision, result.reverted),
                                                             'Decisión registrada.'))
    return hx_trigger(response, 'siiap:review-count',
                      {'count': inbox.pending_total(current_user)})

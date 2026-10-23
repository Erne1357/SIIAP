# app/routes/pages/grade_corrections_pages.py
"""
Page routes for grade corrections (Configuración → Correcciones de
calificaciones, phase 6B2): a teacher asks, postgraduate_admin decides.
Rules live in `grading_service`; the list is an HTML fragment that each
decision refreshes.
"""
from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.services import grading_service
from app.services.errors import ValidationFailed
from app.utils.htmx import hx_flash, is_htmx, render_fragment
from app.utils.permissions import permission_required

pages_grade_corrections = Blueprint('pages_grade_corrections', __name__,
                                    url_prefix='/grade-corrections')

_LIST_PARTIAL = 'grade_corrections/_partials/_list.html'
_WITHDRAWAL_WARNING = ('El estudiante tiene baja definitiva por esta materia: revisa en su '
                       'expediente si corresponde revertirla.')


def _list_fragment():
    return render_fragment(_LIST_PARTIAL, corrections=grading_service.pending_corrections())


@pages_grade_corrections.route('/')
@login_required
@permission_required('grades.page.decide_correction')
def index():
    """Pending correction requests (full page, or just the list for htmx)."""
    if is_htmx():
        return _list_fragment()
    return render_template('grade_corrections/index.html',
                           corrections=grading_service.pending_corrections())


@pages_grade_corrections.route('/<int:correction_id>/decide', methods=['POST'])
@login_required
@permission_required('grades.page.decide_correction')
def decide(correction_id):
    """Approve or reject one request; answers the refreshed list."""
    decision = (request.form.get('decision') or '').strip()
    if decision not in ('approve', 'reject'):
        raise ValidationFailed('Elige aprobar o rechazar la solicitud.')
    approve = decision == 'approve'
    result = grading_service.decide_correction(
        correction_id, approve, request.form.get('notes', ''), current_user.id)
    message = 'Corrección aprobada.' if approve else 'Corrección rechazada.'
    level = 'success'
    if result['review_withdrawal']:
        level, message = 'warning', f'{message} {_WITHDRAWAL_WARNING}'
    elif result.get('special_now_failed'):
        level, message = 'warning', (
            f'{message} Con la corrección el estudiante reprobó un intento especial: '
            'revisa en su expediente si corresponde la baja definitiva.')
    return hx_flash(_list_fragment(), level, message)

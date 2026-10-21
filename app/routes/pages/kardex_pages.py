# app/routes/pages/kardex_pages.py
"""
Page routes for the student's own kardex (Inicio → Mi kardex, phase 6B2).
The record's "Kardex" tab lives with the other record fragments in
`student_record_pages`. Rules live in `kardex_service`.
"""
from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.services import kardex_service
from app.utils.permissions import permission_required

pages_kardex = Blueprint('pages_kardex', __name__, url_prefix='/kardex')


def _own_options() -> list:
    """The current user's enrolled links, ordered by program name."""
    links = [up for up in (current_user.user_program or [])
             if up.admission_status == 'enrolled']
    return sorted(links, key=lambda up: (up.program.name if up.program else '', up.id))


@pages_kardex.route('/')
@login_required
@permission_required('kardex.page.view_own')
def my_kardex():
    """The current student's kardex (`?program=` picks among their own programs)."""
    options = _own_options()
    raw = request.args.get('program')
    if raw is not None:
        try:
            program_id = int(raw)
        except ValueError:
            abort(404)
        up = next((o for o in options if o.program_id == program_id), None)
        if up is None:
            abort(404)
    else:
        up = current_user.current_user_program()
        if up is not None and options and up not in options:
            up = options[0]
    return render_template(
        'kardex/my_kardex.html',
        kd=kardex_service.kardex(up.id) if up is not None else None,
        program_options=options,
        selected_program_id=up.program_id if up is not None else None,
    )

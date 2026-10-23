# app/routes/pages/conclusion_pages.py
"""
Page routes of the conclusion phase for students and thesis advisers (phase 6C).
Rules live in `conclusion_service`; the coordination screens are elsewhere.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services import academic_status_service as status_svc
from app.services import conclusion_service as svc
from app.utils.htmx import hx_flash, is_htmx, render_fragment
from app.utils.permissions import permission_required

pages_conclusion = Blueprint('pages_conclusion', __name__, url_prefix='/conclusion')


def _own_options() -> list:
    """The current user's enrolled links, ordered by program name."""
    links = [up for up in (current_user.user_program or [])
             if up.admission_status == 'enrolled']
    return sorted(links, key=lambda up: (up.program.name if up.program else '', up.id))


def _selected_link(options: list):
    """The link picked by `?program=` (404 if not theirs), else the current one."""
    raw = request.args.get('program')
    if raw is not None:
        try:
            program_id = int(raw)
        except ValueError:
            abort(404)
        up = next((o for o in options if o.program_id == program_id), None)
        if up is None:
            abort(404)
        return up
    up = current_user.current_user_program()
    if up is not None and options and up not in options:
        up = options[0]
    return up


def _context(up) -> dict:
    """Everything the requirements fragment and the page need for one link."""
    graduated = svc.effective_status(up) == status_svc.GRADUATED
    return {
        'up': up,
        'graduated': graduated,
        'requirements': svc.requirements(up),
    }


@pages_conclusion.route('/')
@login_required
@permission_required('conclusion.page.view_own')
def my_conclusion():
    """The student's own conclusion page (`?program=` picks among their programs)."""
    options = _own_options()
    up = _selected_link(options)
    ctx = {}
    if up is not None:
        ctx = _context(up)
        ctx.update(
            thesis=svc.get_thesis(up),
            conditions=svc.conditions(up),
            exams=svc.exams(up),
            exam=svc.current_exam(up),
            progress=svc.progress(up),
            role_labels=svc.ROLE_LABELS_ES,
        )
    return render_template(
        'conclusion/my_conclusion.html',
        program_options=options,
        selected_program_id=up.program_id if up is not None else None,
        **ctx,
    )


@pages_conclusion.route('/requirements/<uuid:archive_uuid>', methods=['POST'])
@login_required
@permission_required('conclusion.page.view_own')
def upload_requirement(archive_uuid):
    """Upload (or replace) a requirement; answers the refreshed requirement list."""
    options = _own_options()
    program_id = request.form.get('program', type=int)
    up = next((o for o in options if o.program_id == program_id), None)
    if up is None:
        abort(404)
    svc.upload_requirement(current_user, archive_uuid, up.id, request.files.get('file'))
    message = 'Documento enviado. Quedó pendiente de revisión.'
    if not is_htmx():
        flash(message, 'success')
        return redirect(url_for('pages_conclusion.my_conclusion', program=up.program_id))
    response = render_fragment('conclusion/_partials/_requirements.html', **_context(up))
    return hx_flash(response, 'success', message)


@pages_conclusion.route('/theses')
@login_required
@permission_required('conclusion.page.my_theses')
def my_theses():
    """Read-only list of the theses where the user sits on the tutorial committee."""
    return render_template(
        'conclusion/my_theses.html',
        rows=svc.my_theses(current_user),
        role_labels=svc.ROLE_LABELS_ES,
        can_view_record=current_user.has_permission('students.page.view_record'),
    )

# app/routes/pages/teaching_pages.py
"""
Page routes for teachers (Docencia → Mis grupos, phase 6B1).

A teacher is whoever a group names as `teacher_id`, whatever their role;
`teaching_scope_service` decides what each user may see.
"""
from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.services import (
    academic_period_service, course_group_service, teaching_scope_service,
)
from app.utils.permissions import permission_required

pages_teaching = Blueprint('pages_teaching', __name__, url_prefix='/teaching')

_ATTEMPT_LABELS = {'ordinary': 'Ordinario', 'repeat': 'Repetición', 'special': 'Especial'}


def _selected_period(periods):
    """The period of `?period=` (an id); the active one, else the newest, by default."""
    raw = (request.args.get('period') or '').strip()
    if raw:
        try:
            wanted = int(raw)
        except ValueError:
            abort(404)
        for period in periods:
            if period.id == wanted:
                return period
        abort(404)
    active = academic_period_service.get_active_period()
    if active is not None:
        return active
    return periods[0] if periods else None


@pages_teaching.route('/')
@login_required
@permission_required('teaching.page.my_groups')
def my_groups():
    """Groups the current user teaches in the selected period."""
    periods = academic_period_service.list_periods_newest_first()
    period = _selected_period(periods)
    groups = (teaching_scope_service.groups_of(current_user.id, period.id)
              if period is not None else [])
    rows = [{'group': g, 'enrolled': course_group_service.enrolled_count(g.id)}
            for g in groups]
    return render_template('teaching/my_groups.html', periods=periods,
                           period=period, rows=rows)


@pages_teaching.route('/groups/<uuid:group_uuid>')
@login_required
@permission_required('teaching.page.my_groups')
def group_detail(group_uuid):
    """Read-only roster of a group the viewer teaches or manages."""
    group = course_group_service.get_group(group_uuid)
    if not teaching_scope_service.can_view_group(current_user, group):
        abort(404)
    return render_template(
        'teaching/group_detail.html', group=group,
        roster=course_group_service.roster(group.id),
        enrolled=course_group_service.enrolled_count(group.id),
        attempt_labels=_ATTEMPT_LABELS)

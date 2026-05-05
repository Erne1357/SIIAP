# app/routes/pages/student_record_pages.py
"""
Page routes for the Student Record (Expediente Completo).
"""
from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from app.models.user import User
from app.services import student_record_service as svc
from app.utils.permissions import permission_required

pages_student_record = Blueprint(
    'pages_student_record',
    __name__,
    url_prefix='/students',
)


@pages_student_record.route('/<int:user_id>/record')
@login_required
@permission_required('students.page.view_record')
def student_record(user_id):
    user = User.query.get(user_id)
    if not user:
        abort(404)

    try:
        if not svc._can_view_record(current_user, user):
            abort(403)
    except Exception:
        abort(403)

    return render_template(
        'coordinator/student_record/index.html',
        target_user=user,
    )

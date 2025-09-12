# app/routes/pages/admin/review_pages.py
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from sqlalchemy.orm import joinedload
from app.utils.auth import roles_required
from app.models import Submission, ProgramStep, User, Program

pages_review = Blueprint("pages_review", __name__, url_prefix="/review")

@pages_review.route("/")
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def index():
    # redirige al listado
    return redirect(url_for("pages_admin.pages_review.submissions"))

@pages_review.route("/submissions")
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def submissions():
    applicant_id = request.args.get('applicant_id', type=int)
    program_id   = request.args.get('program_id',   type=int)
    status       = request.args.get('status',       'pending', type=str)
    sort         = request.args.get('sort',         'desc',    type=str)

    q = Submission.query.filter_by(status=status).join(ProgramStep)

    if applicant_id:
        q = q.filter(Submission.user_id == applicant_id)
    if program_id:
        q = q.filter(ProgramStep.program_id == program_id)

    q = q.options(
        joinedload(Submission.user),
        joinedload(Submission.program_step).joinedload(ProgramStep.program),
        joinedload(Submission.archive),
    )

    q = q.order_by(Submission.upload_date.asc() if sort == 'asc' else Submission.upload_date.desc())
    submissions = q.all()

    applicants = (
        User.query
        .filter(User.role.has(name='applicant'), User.user_program.any())
        .order_by(User.first_name)
        .all()
    )
    programs   = Program.query.order_by(Program.name).all()

    context = {
        'submissions': submissions,
        'filters': {'applicant_id': applicant_id, 'program_id': program_id, 'status': status, 'sort': sort},
        'applicants': applicants,
        'programs': programs,
    }
    return render_template("admin/review/submissions_list.html", **context)

@pages_review.route("/submission/<int:sub_id>")
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def submission_detail(sub_id: int):
    sub = (
        Submission.query
        .options(
            joinedload(Submission.user),
            joinedload(Submission.program_step).joinedload(ProgramStep.program),
            joinedload(Submission.archive),
            joinedload(Submission.program_step).joinedload(ProgramStep.step)
        )
        .get_or_404(sub_id)
    )
    return render_template("admin/review/review_detail.html", sub=sub)

# app/routes/pages/admin/review_pages.py
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.utils.permissions import permission_required
from app.models import Submission, ProgramStep, User, Program
from app.models.archive import Archive
from app.models.step import Step
from app.models.phase import Phase

pages_review = Blueprint("pages_review", __name__, url_prefix="/review")

VALID_PHASES = {'admission', 'permanence', 'conclusion'}


@pages_review.route("/")
@login_required
@permission_required('admin_review.page.view')
def index():
    # redirige al listado
    return redirect(url_for("pages_admin.pages_review.submissions"))


@pages_review.route("/submissions")
@login_required
@permission_required('admin_review.page.view')
def submissions():
    applicant_id = request.args.get('applicant_id', type=int)
    program_id   = request.args.get('program_id',   type=int)
    status       = request.args.get('status',       'pending', type=str)
    sort         = request.args.get('sort',         'asc',     type=str)  # FIFO: más antiguos primero
    show_all     = request.args.get('show_all',     'false',   type=str).lower() == 'true'
    phase        = (request.args.get('phase') or 'admission').lower()
    if phase not in VALID_PHASES:
        phase = 'admission'

    q = (
        Submission.query
        .filter_by(status=status)
        .join(ProgramStep)
        .join(Archive, Submission.archive_id == Archive.id)
        .join(Step, Archive.step_id == Step.id)
        .join(Phase, Step.phase_id == Phase.id)
        .filter(Phase.name == phase)
    )

    # Obtener programas que el coordinador gestiona
    managed_program_ids = []
    is_program_admin = not current_user.has_permission('academic_periods.api.create')

    if is_program_admin:
        managed_program_ids = [p.id for p in Program.query.filter_by(coordinator_id=current_user.id).all()]

        # Por defecto, filtrar solo por programas del coordinador (a menos que show_all=true)
        if not show_all and not program_id:
            if managed_program_ids:
                q = q.filter(ProgramStep.program_id.in_(managed_program_ids))
            else:
                # Si no gestiona ningún programa, no mostrar nada
                q = q.filter(ProgramStep.program_id == -1)

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
    submissions_list = q.all()

    # Filtrar usuarios disponibles según fase: admision -> applicants, permanence/conclusion -> students
    if phase == 'admission':
        role_filter = User.role.has(name='applicant')
    else:
        role_filter = User.role.has(name='student')

    if is_program_admin and managed_program_ids and not show_all:
        from app.models import UserProgram
        applicants = (
            User.query
            .filter(role_filter)
            .join(UserProgram, User.id == UserProgram.user_id)
            .filter(UserProgram.program_id.in_(managed_program_ids))
            .order_by(User.first_name)
            .all()
        )
        programs = Program.query.filter(Program.id.in_(managed_program_ids)).order_by(Program.name).all()
    else:
        applicants = (
            User.query
            .filter(role_filter, User.user_program.any())
            .order_by(User.first_name)
            .all()
        )
        programs = Program.query.order_by(Program.name).all()

    # Conteo de pendientes por fase para los badges en los tabs
    base_count_q = Submission.query.filter_by(status='pending').join(ProgramStep)
    if is_program_admin and managed_program_ids and not show_all and not program_id:
        base_count_q = base_count_q.filter(ProgramStep.program_id.in_(managed_program_ids))
    elif is_program_admin and not managed_program_ids and not show_all:
        base_count_q = base_count_q.filter(ProgramStep.program_id == -1)

    counts_by_phase = {}
    for ph_name in VALID_PHASES:
        counts_by_phase[ph_name] = (
            base_count_q
            .join(Archive, Submission.archive_id == Archive.id)
            .join(Step, Archive.step_id == Step.id)
            .join(Phase, Step.phase_id == Phase.id)
            .filter(Phase.name == ph_name)
            .count()
        )

    context = {
        'submissions': submissions_list,
        'filters': {
            'applicant_id': applicant_id,
            'program_id': program_id,
            'status': status,
            'sort': sort,
            'show_all': show_all,
            'phase': phase,
        },
        'phase_counts': counts_by_phase,
        'applicants': applicants,
        'programs': programs,
        'is_program_admin': is_program_admin,
        'managed_program_ids': managed_program_ids,
    }
    return render_template("admin/review/submissions_list.html", **context)

@pages_review.route("/submission/<int:sub_id>")
@login_required
@permission_required('admin_review.page.view')
def submission_detail(sub_id: int):
    from app.models.user_program import UserProgram
    from app.models.academic_period import AcademicPeriod
    from app.models.document_deadline import DocumentDeadline

    sub = (
        Submission.query
        .options(
            joinedload(Submission.user),
            joinedload(Submission.program_step).joinedload(ProgramStep.program),
            joinedload(Submission.archive),
            joinedload(Submission.program_step).joinedload(ProgramStep.step),
            joinedload(Submission.document_deadline),
            joinedload(Submission.academic_period),
        )
        .get_or_404(sub_id)
    )

    # UserProgram para extraer current_semester si la submission no tiene semester
    up = (
        UserProgram.query
        .filter_by(
            user_id=sub.user_id,
            program_id=(sub.program_step.program_id if sub.program_step else None),
        )
        .first()
    )

    # Historial de versiones previas del MISMO archive del MISMO usuario
    history = (
        Submission.query
        .filter(
            Submission.user_id == sub.user_id,
            Submission.archive_id == sub.archive_id,
            Submission.id != sub.id,
        )
        .order_by(Submission.upload_date.desc())
        .all()
    )

    return render_template(
        "admin/review/review_detail.html",
        sub=sub,
        user_program=up,
        history=history,
    )

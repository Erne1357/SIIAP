from flask import Blueprint, render_template, request, redirect,flash,url_for
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app import db
from app.utils.auth import roles_required
from app.models import Submission, ProgramStep,User, Program

review_bp = Blueprint('review', __name__, url_prefix='/review')


# 1. Ruta raíz /admin/review/ → redirige al listado
@review_bp.route('/')
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def index():
    return redirect(url_for('admin.review.submissions'))


# 2. Listado de submissions pendientes (con filtros y orden)
@review_bp.route('/submissions')
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def submissions():
    # → Parámetros de querystring
    applicant_id = request.args.get('applicant_id', type=int)
    program_id   = request.args.get('program_id',   type=int)
    status       = request.args.get('status',       'pending', type=str)
    sort         = request.args.get('sort',        'desc', type=str)

    # → Base de la consulta
    q = Submission.query.filter_by(status=status)
    q = q.join(ProgramStep)

    # → Aplicar filtros
    if applicant_id:
        q = q.filter(Submission.user_id == applicant_id)
    if program_id:
        q = q.filter(ProgramStep.program_id == program_id)

    # → Cargar relaciones para la tabla
    q = q.options(
        joinedload(Submission.user),
        joinedload(Submission.program_step).joinedload(ProgramStep.program)
    )

    # → Ordenamiento
    if sort == 'asc':
        q = q.order_by(Submission.upload_date.asc())
    else:
        q = q.order_by(Submission.upload_date.desc())

    # Para llenar los select de filtros
    applicants = (
        User.query
        .filter(
            User.role.has(name='applicant'),   
            User.user_program.any()            
        )
        .order_by(User.first_name)            
        .all()                                  
    )
    programs   = Program.query.order_by(Program.name).all()

    submissions = q.all()
    filters = {
        'applicant_id': applicant_id,
        'program_id':   program_id,
        'status':       status,
        'sort':         sort
    }
    context = {
        'submissions': submissions,
        'filters': filters,
        'applicants': applicants,
        'programs': programs
    }
    return render_template(
        'admin/review/submissions_list.html',
        **context
    )


# 3. Vista detalle + visor de un submission
@review_bp.route('/submission/<int:sub_id>')
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def submission_detail(sub_id):
    sub = Submission.query\
        .options(
            joinedload(Submission.user),
            joinedload(Submission.program_step).joinedload(ProgramStep.program)
        )\
        .get_or_404(sub_id)
    return render_template('admin/review/review_detail.html', sub=sub)


# 4. Acción de aprobar/rechazar con comentario
@review_bp.route('/submission/<int:sub_id>/action', methods=['POST'])
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def submission_action(sub_id):
    sub = Submission.query.get_or_404(sub_id)

    action  = request.form.get('action')
    comment = request.form.get('comment', '').strip()

    if action not in ('approve', 'reject'):
        flash('Acción inválida.', 'danger')
        return redirect(url_for('review.submission_detail', sub_id=sub_id))

    # → Actualizar estado y campos de revisión
    sub.status            = 'approved' if action == 'approve' else 'rejected'
    sub.reviewer_id       = current_user.id
    sub.review_date       = db.func.now()
    sub.reviewer_comment  = comment

    db.session.commit()
    flash(f'Documento {"aprobado" if action=="approve" else "rechazado"} con éxito.', 'success')
    return redirect(url_for('admin.review.index'))
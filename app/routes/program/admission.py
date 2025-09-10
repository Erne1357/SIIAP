# app/routes/admission.py
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort
)
from flask_login import login_required, current_user
from app import db
from app.utils.auth import roles_required
from app.utils.files import save_user_doc
from app.utils.utils import getPeriod
from app.services.admission_service import get_admission_state
from app.models import Program, Archive, Submission, UserProgram

admission_bp = Blueprint('admission', __name__, url_prefix='/admission')



@admission_bp.route('/<string:slug>', methods=['GET', 'POST'])
@login_required
@roles_required('applicant')
def admission_dashboard(slug):
    # 1) Validar inscripción
    program = Program.query.filter_by(slug=slug).first_or_404()
    up = UserProgram.query.filter_by(
        program_id=program.id,
        user_id=current_user.id
    ).first()
    if not up:
        flash('Debes inscribirte antes de subir documentos.', 'warning')
        return redirect(url_for('program.view_program', slug=slug))

    # 2) Manejo de POST (subida de archivo)
    if request.method == 'POST':
        archive_id = int(request.form['archive_id'])
        archive = Archive.query.get_or_404(archive_id)

        # bloqueos se calculan en el servicio, pero chequeamos rápido:
        state = get_admission_state(current_user.id, program.id, up)
        if state['lock_info'].get(archive.step.id):
            flash('Debes aprobar el paso anterior.', 'danger')
        else:
            file = request.files.get('file')
            if file:
                rel = save_user_doc(file, current_user.id,
                                    phase='admission', name=archive.name)
                sub = state['subs'].get(archive.id) or Submission(
                    user_id=current_user.id,
                    archive_id=archive.id,
                    program_step_id=archive.step.program_steps[0].id,
                    file_path=rel,
                    period=getPeriod(),
                    semester=0,
                    status='pending'
                )
                sub.upload_date = db.func.now()
                sub.file_path   = rel
                sub.status      = 'pending'
                db.session.add(sub)
                db.session.commit()
                flash('Documento enviado correctamente.', 'success')
        return redirect(
            url_for('program.admission.admission_dashboard', slug=slug)
            + f"#pane-{archive.step.id}"
        )

    # 3) Para GET, delegar TODO al servicio
    context = get_admission_state(current_user.id, program.id, up)
    return render_template(
        'programs/admission/admission_dashboard.html',
        program=program,
        **context
    )

@admission_bp.route('/submission/<int:sub_id>/delete', methods=['POST'])
@login_required
@roles_required('applicant')
def delete_submission(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    if sub.user_id != current_user.id:
        abort(403)
    db.session.delete(sub)
    db.session.commit()
    flash('Archivo eliminado.', 'success')
    return redirect(request.referrer or url_for('program.admission.admission_dashboard',
                         slug=sub.program_step.program.slug))
# app/routes/admission.py  (nuevo blueprint o dentro de program_bp)
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort
)
from flask_login import login_required, current_user
from sqlalchemy.orm import selectinload
from app import db
from app.utils.auth import roles_required
from app.utils.files import save_user_doc
from app.utils.utils import getPeriod
from app.routes.program import program_bp
from app.models import (
    Program, ProgramStep, Step, Archive, Submission, UserProgram, Phase
)

@program_bp.route('/<string:slug>/admission', methods=['GET', 'POST'])
@login_required
@roles_required('applicant')
def admission_dashboard(slug):
    # --- 1. Seguridad: inscrito en el programa ---
    program = Program.query.filter_by(slug=slug).first_or_404()
    if not UserProgram.query.filter_by(program_id=program.id,
                                       user_id=current_user.id).first():
        flash('Debes inscribirte antes de subir documentos.', 'warning')
        return redirect(url_for('program.view_program', slug=slug))

    # --- 2. Consulta de pasos + archivos + submissions del usuario ---
    steps = (
        Step.query
        .join(ProgramStep)
        .join(Phase)                                       # ← nueva unión
        .filter(ProgramStep.program_id == program.id,
                Phase.name == 'admission')                 # ← filtro
        .options(
            selectinload(Step.archives),
            selectinload(Step.program_steps)
        )
        .order_by(ProgramStep.sequence)
        .all()
    )

    # Dict[archive_id] → submission   del usuario
    subs = {s.archive_id: s for s in
            Submission.query
                      .filter_by(user_id=current_user.id)
                      .filter(Submission.archive_id.in_(
                              [a.id for st in steps for a in st.archives]))
                      .all()}

    # --- 3. POST: subir archivo --------------------------------------
    if request.method == 'POST':
        archive_id = int(request.form['archive_id'])
        archive = Archive.query.get_or_404(archive_id)

        # 3-a. ¿Está bloqueado el paso?
        locked, _msg = _step_locked(steps, archive.step.id, subs)
        if locked:
            flash(_msg, 'danger')
            return redirect(request.url)

        # 3-b. Guardar archivo
        file = request.files.get('file')
        if not file:
            flash('Selecciona un archivo.', 'warning')
            return redirect(request.url)

        rel_path = save_user_doc(file, current_user.id, phase='admission', name=archive.name)
        sub = subs.get(archive.id) or Submission(
            user_id=current_user.id,
            archive_id=archive.id,
            program_step_id=archive.step.program_steps[0].id,
            file_path=rel_path,
            period=getPeriod(),
            semester=0,
            status='pending'
        )
        sub.upload_date = db.func.now()  # Actualizar fecha de subida
        sub.file_path = rel_path
        sub.status = 'pending'
        db.session.add(sub)
        db.session.commit()

        flash('Documento enviado correctamente.', 'success')
        return redirect(request.url)

    # --- 4. Render ----------------------------------------------------
    lock_info = {s.id: _step_locked(steps, s.id, subs)[0] for s in steps}

    # Contexto para la plantilla
    context = {
        "program": program,
        "steps": steps,
        "subs": subs,
        "lock_info": lock_info
    }

    return render_template('/programs/admission/dashboard.html', **context)

# --------------------------------------------------------------------
def _step_locked(all_steps, step_id, subs_dict):
    """
    Devuelve (bool bloqueado, msg) para el paso step_id.
    Lógica: si step.sequence == 0  ⇒ nunca bloqueado.
            para los demás: el paso anterior debe tener TODOS sus
            archivos con submission.status == 'approved'.
    """
    prog_step = (ps for st in all_steps for ps in st.program_steps
                 if st.id == step_id).__next__()
    if prog_step.sequence == 0:
        return False, ''

    # Paso anterior
    prev_seq = prog_step.sequence - 1
    if prev_seq == 0:
        return False, ''
    prev_step = next((st for st in all_steps
                      if any(ps.sequence == prev_seq for ps in st.program_steps)), None)
    if not prev_step:
        return False, ''

    for arch in prev_step.archives:
        sub = subs_dict.get(arch.id)
        if not sub or sub.status != 'approved':
            return True, 'Debes tener todos los documentos del paso anterior aprobados.'
    return False, ''

@program_bp.route('/submission/<int:sub_id>/delete', methods=['POST'])
@login_required
@roles_required('applicant')
def delete_submission(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    if sub.user_id != current_user.id:
        abort(403)
    db.session.delete(sub)
    db.session.commit()
    flash('Archivo eliminado.', 'success')
    return redirect(request.referrer or url_for('admission.admission_dashboard',
                         slug=sub.program_step.program.slug))

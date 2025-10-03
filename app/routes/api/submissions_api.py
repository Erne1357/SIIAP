# app/routes/api/submissions_api.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Program, Archive, Submission, UserProgram, ProgramStep
from app.utils.files import save_user_doc
from app.utils.utils import getPeriod
from app.services.admission_service import get_admission_state
import logging

api_submissions = Blueprint("api_submissions", __name__, url_prefix="/api/v1/submissions")

@api_submissions.post("")
@login_required
def upload_submission():
    """
    multipart/form-data:
      - archive_id (int)          obligatorio
      - file (File)               obligatorio
      - program_id (int)          opcional (uno de program_id o program_slug)
      - program_slug (string)     opcional
    """
    archive_id   = request.form.get("archive_id", type=int)
    program_id   = request.form.get("program_id", type=int)
    program_slug = request.form.get("program_slug", type=str)
    file         = request.files.get("file")

    if not archive_id or not file or (not program_id and not program_slug):
        return jsonify({
            "data": None,
            "error": {"code": "BAD_REQUEST", "message": "Faltan parámetros (archive_id, file, program_id/slug)."},
            "meta": {}
        }), 400

    # 1) Archive
    archive = Archive.query.get(archive_id)
    if not archive:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": "Archivo requerido no existe."},
            "meta": {}
        }), 404

    # 2) Programa (id o slug)
    program = (Program.query.get(program_id) if program_id
               else Program.query.filter_by(slug=program_slug).first())
    if not program:
        return jsonify({
            "data": None,
            "error": {"code": "PROGRAM_NOT_FOUND", "message": "Programa no encontrado."},
            "meta": {}
        }), 404

    # 3) Verificar que el step del archive pertenezca a ese programa
    #    (hay un ProgramStep por (program_id, step_id))
    ps = ProgramStep.query.filter_by(program_id=program.id, step_id=archive.step_id).first()
    if not ps:
        return jsonify({
            "data": None,
            "error": {"code": "STEP_NOT_IN_PROGRAM", "message": "El documento no pertenece a este programa."},
            "meta": {}
        }), 409

    # 4) Verificar inscripción del usuario en ese programa
    up = UserProgram.query.filter_by(program_id=program.id, user_id=current_user.id).first()
    current_app.logger.info(
        f"[upload_submission] user={current_user.id} program={program.id if program else None} "
        f"archive={archive.id} step={archive.step_id} ps={ps.id if ps else None} up={bool(up)}"
    )
    if not up:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_ENROLLED", "message": "Debes inscribirte antes de subir documentos."},
            "meta": {}
        }), 403

    # 5) Lock check según el estado de admisión del programa elegido
    state = get_admission_state(current_user.id, program.id, up)
    if state["lock_info"].get(archive.step_id or archive.step.id):
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Debes aprobar el paso anterior."}],
            "error": {"code": "STEP_LOCKED", "message": "Paso bloqueado"},
            "meta": {}
        }), 409

    # 6) Guardar archivo
    rel = save_user_doc(file, current_user.id, phase='admission', name=archive.name)

    # 7) Reusar submission (si existía) o crear
    existing = state["subs"].get(archive.id)
    sub = existing or Submission(
        user_id=current_user.id,
        archive_id=archive.id,
        program_step_id=ps.id,
        file_path=rel,
        period=getPeriod(),
        semester=0,
        uploaded_by=current_user.id,
        uploaded_by_role=current_user.role.name,
        status='pending'
    )

    # Actualizar campos base
    sub.program_step_id = ps.id
    sub.upload_date = db.func.now()
    sub.file_path   = rel
    sub.status      = 'pending'

    db.session.add(sub)
    db.session.commit()

    return jsonify({
        "data": {
            "submission": {
                "id": sub.id,
                "archive_id": sub.archive_id,
                "status": sub.status,
                "file_path": sub.file_path,
                "program_id": program.id,
                "program_step_id": ps.id
            }
        },
        "flash": [{"level": "success", "message": "Documento enviado correctamente."}],
        "error": None,
        "meta": {}
    }), 201

@api_submissions.delete("/<int:sub_id>")
@login_required
def delete_submission(sub_id: int):
    sub = Submission.query.get(sub_id)
    if not sub:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": "Submission no encontrada"}, "meta": {}}), 404
    if sub.user_id != current_user.id:
        return jsonify({"data": None, "error": {"code": "FORBIDDEN", "message": "No puedes borrar este recurso"}, "meta": {}}), 403

    db.session.delete(sub)
    db.session.commit()
    return jsonify({
        "data": True,
        "flash": [{"level": "success", "message": "Archivo eliminado."}],
        "error": None, "meta": {}
    }), 200

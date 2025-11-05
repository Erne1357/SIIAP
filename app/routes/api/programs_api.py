# app/routes/api/programs_api.py
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services import programs_service as svc
from app.services.user_history_service import UserHistoryService

api_programs = Blueprint('api_programs', __name__, url_prefix='/api/v1/programs')

@api_programs.get('/')
@login_required
def api_list_programs():
    items = svc.list_programs()
    data = [{"id": p.id, "name": p.name, "slug": p.slug} for p in items]
    return jsonify({"data": data, "error": None, "meta": {"count": len(data)}}), 200

@api_programs.get('/<string:slug>')
@login_required
def api_get_program(slug):
    try:
        p = svc.get_program_by_slug(slug)
    except svc.ProgramNotFound:
        return jsonify({"data": None, "error": {"code":"NOT_FOUND","message":"Programa no encontrado"}, "meta":{}}), 404
    data = {
        "id": p.id, "name": p.name, "slug": p.slug,
        "steps": [
            {
              "id": ps.step.id,
              "name": ps.step.name,
              "phase": getattr(ps.step.phase, "name", None),
              "archives": [{"id": a.id, "name": a.name} for a in ps.step.archives]
            }
            for ps in p.program_steps
        ]
    }
    return jsonify({"data": data, "error": None, "meta": {}}), 200

@api_programs.post('/<int:program_id>/inscription')
@login_required
@roles_required('applicant')
def api_enroll(program_id):
    try:
        program = svc.enroll_user_once(program_id, current_user.id)
        
        # Registrar en el historial
        try:
            UserHistoryService.log_program_enrollment(
                user_id=current_user.id,
                program_name=program.name,
                program_id=program.id
            )
            from app import db
            db.session.commit()
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error al registrar postulación en historial: {e}")
        
        return jsonify({
            "data": {"program": {"id": program.id, "slug": program.slug}},
            "flash": [{"level": "success", "message": "Te has postulado en el programa."}],
            "error": None, "meta": {}
        }), 200
    except svc.AlreadyEnrolledError as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": str(e)}],
            "error": {"code": "ALREADY_ENROLLED", "message": str(e)},
            "meta": {}
        }), 409
    except svc.ProgramNotFound:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Programa no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Programa no encontrado"},
            "meta": {}
        }), 404

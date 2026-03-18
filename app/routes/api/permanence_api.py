# app/routes/api/permanence_api.py
"""
API para gestionar la permanencia semestral de estudiantes (Fase 6).
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services import permanence_service as svc

api_permanence = Blueprint(
    'api_permanence',
    __name__,
    url_prefix='/api/v1/permanence'
)


@api_permanence.get('/program/<int:program_id>/students')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_get_enrolled_students(program_id):
    """Lista estudiantes inscritos con su estado de permanencia."""
    try:
        data = svc.get_enrolled_students(program_id)
        return jsonify({
            "data": data,
            "error": None,
            "meta": {"count": len(data)}
        }), 200
    except Exception as e:
        return jsonify({
            "data": None,
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_permanence.get('/program/<int:program_id>/stats')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_get_permanence_stats(program_id):
    """Estadisticas de permanencia para un programa."""
    try:
        stats = svc.get_permanence_stats(program_id)
        return jsonify({
            "data": stats,
            "error": None,
            "meta": {}
        }), 200
    except Exception as e:
        return jsonify({
            "data": None,
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_permanence.post('/user-program/<int:user_program_id>/confirm')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_confirm_semester_enrollment(user_program_id):
    """El coordinador confirma la inscripcion semestral de un estudiante."""
    data = request.get_json() or {}
    academic_period_id = data.get('academic_period_id')
    notes = (data.get('notes') or '').strip() or None

    if not academic_period_id:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Falta el periodo academico"}],
            "error": {"code": "MISSING_FIELD", "message": "academic_period_id es requerido"},
            "meta": {}
        }), 400

    try:
        se = svc.confirm_semester_enrollment(
            user_program_id=user_program_id,
            academic_period_id=academic_period_id,
            coordinator_id=current_user.id,
            notes=notes
        )
        return jsonify({
            "data": se.to_dict(),
            "flash": [{"level": "success", "message": f"Inscripcion del semestre {se.semester_number} confirmada"}],
            "error": None,
            "meta": {}
        }), 200

    except svc.StudentNotFound as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404

    except svc.InvalidStateTransition as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": str(e)}],
            "error": {"code": "INVALID_STATE", "message": str(e)},
            "meta": {}
        }), 400

    except Exception as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al confirmar inscripcion"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_permanence.patch('/semester-enrollment/<int:semester_enrollment_id>/status')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_update_enrollment_status(semester_enrollment_id):
    """Actualiza el estado de una inscripcion semestral."""
    data = request.get_json() or {}
    new_status = (data.get('status') or '').strip()
    notes = (data.get('notes') or '').strip() or None

    if not new_status:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Falta el nuevo estado"}],
            "error": {"code": "MISSING_FIELD", "message": "status es requerido"},
            "meta": {}
        }), 400

    try:
        se = svc.update_enrollment_status(
            semester_enrollment_id=semester_enrollment_id,
            new_status=new_status,
            coordinator_id=current_user.id,
            notes=notes
        )
        STATUS_LABELS = {
            'active': 'Activo',
            'completed': 'Completado',
            'on_leave': 'Baja temporal',
            'dropped': 'Baja definitiva',
        }
        label = STATUS_LABELS.get(new_status, new_status)
        return jsonify({
            "data": se.to_dict(),
            "flash": [{"level": "success", "message": f"Estado actualizado a: {label}"}],
            "error": None,
            "meta": {}
        }), 200

    except svc.StudentNotFound as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404

    except ValueError as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": str(e)}],
            "error": {"code": "INVALID_DATA", "message": str(e)},
            "meta": {}
        }), 400

    except Exception as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al actualizar estado"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_permanence.get('/user-program/<int:user_program_id>/status')
@login_required
def api_get_student_permanence(user_program_id):
    """
    Obtiene el estado de permanencia de un estudiante.
    El propio estudiante puede ver el suyo; coordinadores pueden ver cualquiera.
    """
    from app.models import UserProgram
    up = UserProgram.query.get(user_program_id)
    if not up:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": "UserProgram no encontrado"},
            "meta": {}
        }), 404

    if current_user.id != up.user_id:
        if not hasattr(current_user, 'role') or current_user.role.name not in (
            'coordinator', 'program_admin', 'postgraduate_admin'
        ):
            return jsonify({
                "data": None,
                "error": {"code": "FORBIDDEN", "message": "No tienes permiso"},
                "meta": {}
            }), 403

    try:
        data = svc.get_student_permanence(user_program_id)
        return jsonify({
            "data": data,
            "error": None,
            "meta": {}
        }), 200
    except Exception as e:
        return jsonify({
            "data": None,
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500

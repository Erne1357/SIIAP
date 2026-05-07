# app/routes/api/deliberation_api.py
"""
API para gestionar el proceso de deliberacion de aspirantes.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.utils.permissions import permission_required
from app.services import deliberation_service as svc

api_deliberation = Blueprint(
    'api_deliberation',
    __name__,
    url_prefix='/api/v1/deliberation'
)


@api_deliberation.get('/program/<int:program_id>/applicants')
@login_required
@permission_required('deliberation.api.list_applicants', program_id_kwarg='program_id')
def api_get_applicants_for_deliberation(program_id):
    """Obtiene aspirantes en estado de deliberacion para un programa."""
    try:
        applicants = svc.get_applicants_for_deliberation(program_id)

        data = []
        for up in applicants:
            user = up.user
            data.append({
                'user_program': up.to_dict(include_deliberation=True),
                'user': {
                    'id': user.id,
                    'full_name': f"{user.first_name} {user.last_name} {user.mother_last_name or ''}".strip(),
                    'email': user.email,
                    'curp': user.curp
                }
            })

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


@api_deliberation.get('/program/<int:program_id>/stats')
@login_required
@permission_required('deliberation.api.list_applicants', program_id_kwarg='program_id')
def api_get_deliberation_stats(program_id):
    """Obtiene estadisticas de deliberacion para un programa."""
    try:
        stats = svc.get_deliberation_stats(program_id)

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


@api_deliberation.get('/program/<int:program_id>/by-status/<string:status>')
@login_required
@permission_required('deliberation.api.list_applicants', program_id_kwarg='program_id')
def api_get_applicants_by_status(program_id, status):
    """Obtiene aspirantes de un programa por estado."""
    valid_statuses = ['in_progress', 'interview_completed', 'deliberation',
                      'accepted', 'rejected', 'deferred', 'enrolled']

    if status not in valid_statuses:
        return jsonify({
            "data": None,
            "error": {"code": "INVALID_STATUS", "message": f"Estado invalido: {status}"},
            "meta": {}
        }), 400

    try:
        applicants = svc.get_applicants_by_status(program_id, status)

        data = []
        for up in applicants:
            user = up.user
            data.append({
                'user_program': up.to_dict(include_deliberation=True),
                'user': {
                    'id': user.id,
                    'full_name': f"{user.first_name} {user.last_name} {user.mother_last_name or ''}".strip(),
                    'email': user.email
                }
            })

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


@api_deliberation.post('/user/<int:user_id>/program/<int:program_id>/interview-completed')
@login_required
@permission_required('deliberation.api.decide', program_id_kwarg='program_id')
def api_mark_interview_completed(user_id, program_id):
    """Marca que un aspirante completo su entrevista."""
    try:
        up = svc.mark_interview_completed(user_id, program_id, coordinator_id=current_user.id)

        return jsonify({
            "data": up.to_dict(include_deliberation=True),
            "flash": [{"level": "success", "message": "Entrevista marcada como completada"}],
            "error": None,
            "meta": {}
        }), 200

    except svc.ApplicantNotFound as e:
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
            "flash": [{"level": "danger", "message": "Error al marcar entrevista"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_deliberation.post('/user/<int:user_id>/program/<int:program_id>/start')
@login_required
@permission_required('deliberation.api.decide', program_id_kwarg='program_id')
def api_start_deliberation(user_id, program_id):
    """Inicia el proceso de deliberacion para un aspirante."""
    try:
        up = svc.start_deliberation(user_id, program_id, current_user.id)

        return jsonify({
            "data": up.to_dict(include_deliberation=True),
            "flash": [{"level": "success", "message": "Deliberacion iniciada"}],
            "error": None,
            "meta": {}
        }), 200

    except svc.ApplicantNotFound as e:
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
            "flash": [{"level": "danger", "message": "Error al iniciar deliberacion"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_deliberation.post('/user/<int:user_id>/program/<int:program_id>/accept')
@login_required
@permission_required('deliberation.api.decide', program_id_kwarg='program_id')
def api_accept_applicant(user_id, program_id):
    """Acepta a un aspirante en el programa. Acepta JSON o multipart/form-data
    (cuando is_conditional=true, debe enviarse multipart con dictamen_file)."""
    is_multipart = request.content_type and request.content_type.startswith('multipart/')
    if is_multipart:
        notes = request.form.get('notes')
        is_conditional = str(request.form.get('is_conditional', '')).lower() in ('true', '1', 'yes', 'on')
        dictamen_file = request.files.get('dictamen_file')
    else:
        data = request.get_json() or {}
        notes = data.get('notes')
        is_conditional = bool(data.get('is_conditional', False))
        dictamen_file = None

    try:
        up = svc.accept_applicant(
            user_id, program_id, current_user.id, notes,
            is_conditional=is_conditional,
            dictamen_file=dictamen_file,
        )

        success_msg = (
            "Aceptación condicionada registrada con dictamen"
            if is_conditional else
            "Aspirante aceptado exitosamente"
        )
        return jsonify({
            "data": up.to_dict(include_deliberation=True),
            "flash": [{"level": "success", "message": success_msg}],
            "error": None,
            "meta": {}
        }), 200

    except svc.ApplicantNotFound as e:
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
            "flash": [{"level": "danger", "message": "Error al aceptar aspirante"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_deliberation.post('/user/<int:user_id>/program/<int:program_id>/reject')
@login_required
@permission_required('deliberation.api.decide', program_id_kwarg='program_id')
def api_reject_applicant(user_id, program_id):
    """Rechaza a un aspirante."""
    data = request.get_json() or {}
    rejection_type = data.get('rejection_type', 'full')
    notes = data.get('notes')
    correction_required = data.get('correction_required')

    try:
        up = svc.reject_applicant(
            user_id, program_id, current_user.id,
            rejection_type=rejection_type,
            notes=notes,
            correction_required=correction_required
        )

        msg = "Aspirante rechazado" if rejection_type == 'full' else "Correcciones solicitadas al aspirante"

        return jsonify({
            "data": up.to_dict(include_deliberation=True),
            "flash": [{"level": "success", "message": msg}],
            "error": None,
            "meta": {}
        }), 200

    except svc.ApplicantNotFound as e:
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

    except ValueError as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "INVALID_DATA", "message": str(e)},
            "meta": {}
        }), 400

    except Exception as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al rechazar aspirante"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_deliberation.post('/user/<int:user_id>/program/<int:program_id>/reset')
@login_required
@permission_required('deliberation.api.decide', program_id_kwarg='program_id')
def api_reset_applicant(user_id, program_id):
    """Reinicia el estado de un aspirante a 'in_progress' (despues de correcciones)."""
    data = request.get_json() or {}
    reason = data.get('reason')

    try:
        up = svc.reset_to_in_progress(user_id, program_id, current_user.id, reason)

        return jsonify({
            "data": up.to_dict(include_deliberation=True),
            "flash": [{"level": "success", "message": "Estado del aspirante reiniciado"}],
            "error": None,
            "meta": {}
        }), 200

    except svc.ApplicantNotFound as e:
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
            "flash": [{"level": "danger", "message": "Error al reiniciar estado"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_deliberation.get('/program/<int:program_id>/pending-interview')
@login_required
@permission_required('deliberation.api.list_applicants', program_id_kwarg='program_id')
def api_get_applicants_pending_interview(program_id):
    """Obtiene aspirantes con entrevista reservada pero aun en in_progress."""
    try:
        applicants = svc.get_applicants_with_pending_interview(program_id)

        data = []
        for up in applicants:
            user = up.user
            data.append({
                'user_program': up.to_dict(include_deliberation=True),
                'user': {
                    'id': user.id,
                    'full_name': f"{user.first_name} {user.last_name} {user.mother_last_name or ''}".strip(),
                    'email': user.email,
                    'curp': user.curp
                }
            })

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


@api_deliberation.get('/user/<int:user_id>/program/<int:program_id>/status')
@login_required
def api_get_user_deliberation_status(user_id, program_id):
    """Obtiene el estado de deliberacion de un usuario (aspirante puede ver el suyo)."""
    # Verificar que el usuario sea el mismo o sea coordinador/admin
    if current_user.id != user_id:
        if not current_user.has_permission('deliberation.api.list_applicants'):
            return jsonify({
                "data": None,
                "error": {"code": "FORBIDDEN", "message": "No tienes permiso para ver este estado"},
                "meta": {}
            }), 403

    try:
        up = svc.get_user_program(user_id, program_id)

        return jsonify({
            "data": up.to_dict(include_deliberation=True),
            "error": None,
            "meta": {}
        }), 200

    except svc.ApplicantNotFound as e:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404

    except Exception as e:
        return jsonify({
            "data": None,
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_deliberation.get('/program/<int:program_id>/admission-archives')
@login_required
@permission_required('deliberation.api.list_applicants', program_id_kwarg='program_id')
def api_get_program_admission_archives(program_id):
    """Obtiene los archivos uploadables de la fase de admisión de un programa (para rechazo parcial)."""
    try:
        from app.models import Step, ProgramStep, Phase
        from app.models.archive import Archive
        from sqlalchemy import and_

        archives = (
            Archive.query
            .join(Step, Archive.step_id == Step.id)
            .join(ProgramStep, Step.id == ProgramStep.step_id)
            .join(Phase, Step.phase_id == Phase.id)
            .filter(
                and_(
                    ProgramStep.program_id == program_id,
                    Phase.name == 'admission',
                    Archive.is_uploadable == True  # noqa: E712
                )
            )
            .order_by(ProgramStep.sequence, Archive.id)
            .all()
        )

        data = [{'id': a.id, 'name': a.name} for a in archives]

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


@api_deliberation.post('/user/<int:user_id>/program/<int:program_id>/force-reset')
@login_required
@permission_required('deliberation.api.force_reset', program_id_kwarg='program_id')
def api_force_reset_applicant(user_id, program_id):
    """Reinicio forzado del estado de admisión a 'in_progress'. Solo postgraduate_admin."""
    data = request.get_json() or {}
    reason = data.get('reason', 'Reinicio administrativo')

    try:
        up = svc.force_reset_applicant(user_id, program_id, current_user.id, reason)

        return jsonify({
            "data": up.to_dict(include_deliberation=True),
            "flash": [{"level": "success", "message": "Estado reiniciado a 'En Proceso'"}],
            "error": None,
            "meta": {}
        }), 200

    except svc.ApplicantNotFound as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404

    except Exception as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500

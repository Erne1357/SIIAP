# app/routes/api/acceptance_api.py
"""
API para gestionar los documentos de aceptacion e inscripcion (Fase 4).
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services import acceptance_service as svc

api_acceptance = Blueprint(
    'api_acceptance',
    __name__,
    url_prefix='/api/v1/acceptance'
)


@api_acceptance.get('/program/<int:program_id>/applicants')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_get_accepted_applicants(program_id):
    """Obtiene aspirantes aceptados con estado de sus documentos."""
    try:
        data = svc.get_accepted_applicants(program_id)
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


@api_acceptance.get('/program/<int:program_id>/stats')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_get_acceptance_stats(program_id):
    """Obtiene estadisticas de documentos de aceptacion para un programa."""
    try:
        stats = svc.get_acceptance_stats(program_id)
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


@api_acceptance.get('/user/<int:user_id>/program/<int:program_id>/status')
@login_required
def api_get_acceptance_status(user_id, program_id):
    """Obtiene el estado de los documentos de aceptacion de un aspirante."""
    # El aspirante puede ver los suyos; coordinadores pueden ver cualquiera
    if current_user.id != user_id:
        if not hasattr(current_user, 'role') or current_user.role.name not in (
            'coordinator', 'program_admin', 'postgraduate_admin'
        ):
            return jsonify({
                "data": None,
                "error": {"code": "FORBIDDEN", "message": "No tienes permiso"},
                "meta": {}
            }), 403

    try:
        from app.models import UserProgram
        up = UserProgram.query.filter_by(user_id=user_id, program_id=program_id).first()
        if not up:
            return jsonify({
                "data": None,
                "error": {"code": "NOT_FOUND", "message": "UserProgram no encontrado"},
                "meta": {}
            }), 404

        data = svc.get_acceptance_status(up.id)
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


@api_acceptance.post('/user/<int:user_id>/program/<int:program_id>/upload-doc')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_upload_coordinator_doc(user_id, program_id):
    """El coordinador sube carta de aceptacion o tira de materias."""
    document_type = request.form.get('document_type')
    file = request.files.get('file')

    if not document_type:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Falta el tipo de documento"}],
            "error": {"code": "MISSING_FIELD", "message": "document_type es requerido"},
            "meta": {}
        }), 400

    if not file or file.filename == '':
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No se envio ningun archivo"}],
            "error": {"code": "MISSING_FILE", "message": "Archivo requerido"},
            "meta": {}
        }), 400

    try:
        doc = svc.upload_coordinator_doc(
            user_id=user_id,
            program_id=program_id,
            document_type=document_type,
            file_storage=file,
            coordinator_id=current_user.id
        )
        label = svc.DOC_TYPE_LABELS.get(document_type, document_type)
        return jsonify({
            "data": doc.to_dict(),
            "flash": [{"level": "success", "message": f"{label} subida exitosamente"}],
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

    except svc.InvalidDocumentType as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "INVALID_DOC_TYPE", "message": str(e)},
            "meta": {}
        }), 400

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
            "flash": [{"level": "danger", "message": "Error al subir el documento"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_acceptance.post('/user/<int:user_id>/program/<int:program_id>/submit-receipt')
@login_required
def api_submit_enrollment_receipt(user_id, program_id):
    """El aspirante sube su boleta de servicios escolares."""
    # Solo el propio aspirante puede subir su boleta
    if current_user.id != user_id:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Solo puedes subir tu propia boleta"}],
            "error": {"code": "FORBIDDEN", "message": "No autorizado"},
            "meta": {}
        }), 403

    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No se envio ningun archivo"}],
            "error": {"code": "MISSING_FILE", "message": "Archivo requerido"},
            "meta": {}
        }), 400

    try:
        doc = svc.submit_enrollment_receipt(
            user_id=user_id,
            program_id=program_id,
            file_storage=file,
            aspirant_id=current_user.id
        )
        return jsonify({
            "data": doc.to_dict(),
            "flash": [{"level": "success", "message": "Boleta enviada correctamente. Espera la revision del coordinador."}],
            "error": None,
            "meta": {}
        }), 200

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
            "flash": [{"level": "danger", "message": "Error al enviar la boleta"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_acceptance.post('/document/<int:doc_id>/review')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_review_enrollment_receipt(doc_id):
    """El coordinador aprueba o rechaza la boleta del aspirante."""
    data = request.get_json() or {}
    status = data.get('status')
    notes = data.get('notes')

    if not status:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Falta el estado de revision"}],
            "error": {"code": "MISSING_FIELD", "message": "status es requerido"},
            "meta": {}
        }), 400

    if status == 'rejected' and not notes:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": "Debes indicar el motivo del rechazo"}],
            "error": {"code": "MISSING_NOTES", "message": "Las notas son requeridas al rechazar"},
            "meta": {}
        }), 400

    try:
        doc = svc.review_enrollment_receipt(
            doc_id=doc_id,
            coordinator_id=current_user.id,
            status=status,
            notes=notes
        )
        msg = "Boleta aprobada exitosamente" if status == 'approved' else "Boleta rechazada"
        return jsonify({
            "data": doc.to_dict(),
            "flash": [{"level": "success" if status == 'approved' else "warning", "message": msg}],
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

    except (svc.InvalidDocumentType, svc.InvalidStateTransition) as e:
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
            "flash": [{"level": "danger", "message": "Error al revisar la boleta"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_acceptance.delete('/document/<int:doc_id>')
@login_required
@roles_required('coordinator', 'program_admin', 'postgraduate_admin')
def api_delete_coordinator_doc(doc_id):
    """Elimina un documento de aceptacion subido por el coordinador."""
    try:
        svc.delete_coordinator_doc(doc_id=doc_id, coordinator_id=current_user.id)
        return jsonify({
            "data": None,
            "flash": [{"level": "success", "message": "Documento eliminado"}],
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

    except svc.InvalidDocumentType as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": str(e)}],
            "error": {"code": "INVALID_DOC_TYPE", "message": str(e)},
            "meta": {}
        }), 400

    except Exception as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al eliminar el documento"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500

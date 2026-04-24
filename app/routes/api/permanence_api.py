# app/routes/api/permanence_api.py
"""
API para gestionar la permanencia semestral de estudiantes (Fase 6).
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.utils.permissions import permission_required
from app.models.user_program import UserProgram
from app.services import permanence_service as svc

api_permanence = Blueprint(
    'api_permanence',
    __name__,
    url_prefix='/api/v1/permanence'
)


@api_permanence.get('/program/<int:program_id>/students')
@login_required
@permission_required('permanence.api.list_students', program_id_kwarg='program_id')
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
@permission_required('permanence.api.list_students', program_id_kwarg='program_id')
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
@permission_required('permanence.api.confirm_enrollment')
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
@permission_required('permanence.api.confirm_enrollment')
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
        if not current_user.has_permission('permanence.api.list_students'):
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


# ── Ventanas de entrega (Coordinador) ─────────────────────────────────────────

@api_permanence.get('/program/<int:program_id>/deadlines')
@login_required
@permission_required('permanence.api.manage_deadlines', program_id_kwarg='program_id')
def api_get_deadlines(program_id):
    """Lista ventanas de entrega del periodo activo para un programa."""
    period_id = request.args.get('period_id', type=int)
    try:
        data = svc.get_deadlines_for_program(program_id, academic_period_id=period_id)
        return jsonify({"data": data, "error": None, "meta": {"count": len(data)}}), 200
    except Exception as e:
        return jsonify({"data": None, "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


@api_permanence.post('/program/<int:program_id>/deadlines')
@login_required
@permission_required('permanence.api.manage_deadlines', program_id_kwarg='program_id')
def api_create_deadline(program_id):
    """Crea una ventana de entrega. Body: {archive_id, label, sequence, academic_period_id, opens_at?, closes_at?}"""
    from datetime import datetime
    data = request.get_json() or {}
    archive_id = data.get('archive_id')
    label = (data.get('label') or '').strip()
    sequence = data.get('sequence', 1)
    academic_period_id = data.get('academic_period_id')
    opens_at_raw = data.get('opens_at')
    closes_at_raw = data.get('closes_at')

    if not archive_id or not label:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "archive_id y label son requeridos"}],
            "error": {"code": "MISSING_FIELD", "message": "archive_id y label son requeridos"},
            "meta": {}
        }), 400

    if not academic_period_id:
        from app.models.academic_period import AcademicPeriod
        period = AcademicPeriod.get_active_period()
        if not period:
            return jsonify({
                "data": None,
                "flash": [{"level": "danger", "message": "No hay periodo académico activo"}],
                "error": {"code": "NO_ACTIVE_PERIOD", "message": "No hay periodo académico activo"},
                "meta": {}
            }), 400
        academic_period_id = period.id

    opens_at = datetime.fromisoformat(opens_at_raw) if opens_at_raw else None
    closes_at = datetime.fromisoformat(closes_at_raw) if closes_at_raw else None

    try:
        dl = svc.create_document_deadline(
            program_id=program_id,
            archive_id=archive_id,
            academic_period_id=academic_period_id,
            label=label,
            sequence=int(sequence),
            opens_at=opens_at,
            closes_at=closes_at,
            coordinator_id=current_user.id,
        )
        return jsonify({
            "data": dl.to_dict(),
            "flash": [{"level": "success", "message": f'Ventana "{dl.label}" creada correctamente'}],
            "error": None,
            "meta": {}
        }), 201
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
            "flash": [{"level": "danger", "message": "Error al crear ventana"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_permanence.patch('/deadlines/<int:deadline_id>/toggle')
@login_required
@permission_required('permanence.api.manage_deadlines')
def api_toggle_deadline(deadline_id):
    """Abre/cierra manualmente una ventana. Body: {is_open: bool}"""
    data = request.get_json() or {}
    if 'is_open' not in data:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Campo is_open requerido"}],
            "error": {"code": "MISSING_FIELD", "message": "is_open es requerido"},
            "meta": {}
        }), 400
    try:
        dl = svc.toggle_document_deadline(
            deadline_id=deadline_id,
            is_open=bool(data['is_open']),
            coordinator_id=current_user.id,
        )
        state = 'abierta' if dl.is_open else 'cerrada'
        return jsonify({
            "data": dl.to_dict(),
            "flash": [{"level": "success", "message": f'Ventana "{dl.label}" {state}'}],
            "error": None,
            "meta": {}
        }), 200
    except svc.StudentNotFound as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": str(e)}],
                        "error": {"code": "NOT_FOUND", "message": str(e)}, "meta": {}}), 404
    except Exception as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": "Error al actualizar ventana"}],
                        "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


@api_permanence.delete('/deadlines/<int:deadline_id>')
@login_required
@permission_required('permanence.api.manage_deadlines')
def api_delete_deadline(deadline_id):
    """Elimina una ventana (solo si no tiene submissions)."""
    try:
        svc.delete_document_deadline(deadline_id=deadline_id, coordinator_id=current_user.id)
        return jsonify({
            "data": None,
            "flash": [{"level": "success", "message": "Ventana eliminada"}],
            "error": None,
            "meta": {}
        }), 200
    except svc.StudentNotFound as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": str(e)}],
                        "error": {"code": "NOT_FOUND", "message": str(e)}, "meta": {}}), 404
    except svc.InvalidStateTransition as e:
        return jsonify({"data": None, "flash": [{"level": "warning", "message": str(e)}],
                        "error": {"code": "INVALID_STATE", "message": str(e)}, "meta": {}}), 400
    except Exception as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": "Error al eliminar ventana"}],
                        "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


# ── Documentos del estudiante ──────────────────────────────────────────────────

@api_permanence.get('/user-program/<int:user_program_id>/documents')
@login_required
def api_get_student_documents(user_program_id):
    """Lista ventanas y estado de submission del estudiante en el periodo activo."""
    up = UserProgram.query.get(user_program_id)
    if not up:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": "UserProgram no encontrado"}, "meta": {}}), 404

    if current_user.id != up.user_id:
        if not current_user.has_permission('permanence.api.list_students'):
            return jsonify({"data": None, "error": {"code": "FORBIDDEN", "message": "Sin permiso"}, "meta": {}}), 403

    try:
        data = svc.get_student_documents_for_period(user_program_id)
        return jsonify({"data": data, "error": None, "meta": {"count": len(data)}}), 200
    except svc.StudentNotFound as e:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": str(e)}, "meta": {}}), 404
    except Exception as e:
        return jsonify({"data": None, "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


@api_permanence.post('/user-program/<int:user_program_id>/documents/<int:deadline_id>')
@login_required
def api_submit_permanence_document(user_program_id, deadline_id):
    """El estudiante sube un documento para una ventana de entrega. Multipart con field 'file'."""
    from flask import request as req
    file = req.files.get('file')
    if not file or not file.filename:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No se recibió ningún archivo"}],
            "error": {"code": "MISSING_FILE", "message": "Campo 'file' requerido"},
            "meta": {}
        }), 400

    try:
        sub = svc.submit_permanence_document(
            user_program_id=user_program_id,
            document_deadline_id=deadline_id,
            file_storage=file,
            student_id=current_user.id,
        )
        return jsonify({
            "data": sub,
            "flash": [{"level": "success", "message": "Documento enviado correctamente. Espera la revisión del coordinador."}],
            "error": None,
            "meta": {}
        }), 201
    except svc.StudentNotFound as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": str(e)}],
                        "error": {"code": "NOT_FOUND", "message": str(e)}, "meta": {}}), 404
    except svc.InvalidStateTransition as e:
        return jsonify({"data": None, "flash": [{"level": "warning", "message": str(e)}],
                        "error": {"code": "INVALID_STATE", "message": str(e)}, "meta": {}}), 400
    except Exception as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": "Error al subir documento"}],
                        "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


# ── Revisión de documentos (Coordinador) ──────────────────────────────────────

@api_permanence.get('/program/<int:program_id>/pending-documents')
@login_required
@permission_required('permanence.api.review_doc', program_id_kwarg='program_id')
def api_get_pending_documents(program_id):
    """Lista submissions de permanencia en estado 'review' para el programa."""
    try:
        data = svc.get_pending_documents(program_id)
        return jsonify({"data": data, "error": None, "meta": {"count": len(data)}}), 200
    except Exception as e:
        return jsonify({"data": None, "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


@api_permanence.post('/submissions/<int:submission_id>/review')
@login_required
@permission_required('permanence.api.review_doc')
def api_review_permanence_document(submission_id):
    """Aprueba o rechaza un documento. Body: {status: 'approved'|'rejected', notes?: str}"""
    data = request.get_json() or {}
    status = (data.get('status') or '').strip()
    notes = (data.get('notes') or '').strip() or None

    if status not in ('approved', 'rejected'):
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "status debe ser 'approved' o 'rejected'"}],
            "error": {"code": "INVALID_DATA", "message": "status inválido"},
            "meta": {}
        }), 400

    try:
        sub = svc.review_permanence_document(
            submission_id=submission_id,
            coordinator_id=current_user.id,
            status=status,
            notes=notes,
        )
        action = 'aprobado' if status == 'approved' else 'rechazado'
        return jsonify({
            "data": sub,
            "flash": [{"level": "success", "message": f"Documento {action} correctamente"}],
            "error": None,
            "meta": {}
        }), 200
    except svc.StudentNotFound as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": str(e)}],
                        "error": {"code": "NOT_FOUND", "message": str(e)}, "meta": {}}), 404
    except (svc.InvalidStateTransition, ValueError) as e:
        return jsonify({"data": None, "flash": [{"level": "warning", "message": str(e)}],
                        "error": {"code": "INVALID_STATE", "message": str(e)}, "meta": {}}), 400
    except Exception as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": "Error al revisar documento"}],
                        "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


# ── Referencia Bancaria ────────────────────────────────────────────────────────

@api_permanence.get('/user-program/<int:user_program_id>/payment-reference')
@login_required
def api_get_payment_reference(user_program_id):
    """
    Retorna la referencia bancaria del estudiante para el periodo activo.
    Si no está configurada, retorna configured=False (no es error HTTP).
    """
    from app.services.payment_reference_service import get_payment_reference_for_student

    up = UserProgram.query.get(user_program_id)
    if not up:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": "UserProgram no encontrado"},
            "meta": {}
        }), 404

    if current_user.id != up.user_id:
        if not current_user.has_permission('permanence.api.list_students'):
            return jsonify({
                "data": None,
                "error": {"code": "FORBIDDEN", "message": "Sin permiso"},
                "meta": {}
            }), 403

    try:
        data = get_payment_reference_for_student(user_program_id)
        return jsonify({"data": data, "error": None, "meta": {}}), 200
    except Exception as e:
        return jsonify({
            "data": None,
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


# ── Solicitudes de Baja Temporal ──────────────────────────────────────────────

@api_permanence.get('/program/<int:program_id>/leave-requests')
@login_required
@permission_required('permanence.api.review_doc', program_id_kwarg='program_id')
def api_get_pending_leave_requests(program_id):
    """Lista solicitudes de baja temporal en estado 'review' para el programa."""
    try:
        data = svc.get_pending_leave_requests(program_id)
        return jsonify({"data": data, "error": None, "meta": {"count": len(data)}}), 200
    except Exception as e:
        return jsonify({"data": None, "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


@api_permanence.get('/user-program/<int:user_program_id>/leave-request')
@login_required
def api_get_student_leave_request(user_program_id):
    """Retorna el estado de la solicitud de baja temporal del estudiante."""
    up = UserProgram.query.get(user_program_id)
    if not up:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": "UserProgram no encontrado"}, "meta": {}}), 404

    if current_user.id != up.user_id:
        if not current_user.has_permission('permanence.api.list_students'):
            return jsonify({"data": None, "error": {"code": "FORBIDDEN", "message": "Sin permiso"}, "meta": {}}), 403

    try:
        data = svc.get_student_leave_request(user_program_id)
        return jsonify({"data": data, "error": None, "meta": {}}), 200
    except svc.StudentNotFound as e:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": str(e)}, "meta": {}}), 404
    except Exception as e:
        return jsonify({"data": None, "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


@api_permanence.post('/user-program/<int:user_program_id>/leave-request')
@login_required
def api_submit_leave_request(user_program_id):
    """El estudiante sube la Solicitud de Baja Temporal (multipart, field 'file')."""
    from flask import request as req
    file = req.files.get('file')
    if not file or not file.filename:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No se recibió ningún archivo"}],
            "error": {"code": "MISSING_FILE", "message": "Campo 'file' requerido"},
            "meta": {}
        }), 400

    try:
        sub = svc.submit_leave_request(
            user_program_id=user_program_id,
            file_storage=file,
            student_id=current_user.id,
        )
        return jsonify({
            "data": sub,
            "flash": [{"level": "success", "message": "Solicitud enviada. El coordinador la revisará a la brevedad."}],
            "error": None,
            "meta": {}
        }), 201
    except svc.StudentNotFound as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": str(e)}],
                        "error": {"code": "NOT_FOUND", "message": str(e)}, "meta": {}}), 404
    except svc.InvalidStateTransition as e:
        return jsonify({"data": None, "flash": [{"level": "warning", "message": str(e)}],
                        "error": {"code": "INVALID_STATE", "message": str(e)}, "meta": {}}), 400
    except Exception as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": "Error al subir la solicitud"}],
                        "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


@api_permanence.post('/submissions/<int:submission_id>/leave-request')
@login_required
@permission_required('permanence.api.review_doc')
def api_process_leave_request(submission_id):
    """Aprueba o rechaza una solicitud de baja temporal. Body: {approve: bool, notes?: str}"""
    data = request.get_json() or {}
    approve = data.get('approve')
    notes = (data.get('notes') or '').strip() or None

    if approve is None:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "El campo 'approve' es requerido"}],
            "error": {"code": "MISSING_FIELD", "message": "approve es requerido"},
            "meta": {}
        }), 400

    try:
        result = svc.process_leave_request(
            submission_id=submission_id,
            coordinator_id=current_user.id,
            approve=bool(approve),
            notes=notes,
        )
        action = 'aprobada' if approve else 'rechazada'
        return jsonify({
            "data": result,
            "flash": [{"level": "success", "message": f"Solicitud de baja temporal {action}"}],
            "error": None,
            "meta": {}
        }), 200
    except svc.StudentNotFound as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": str(e)}],
                        "error": {"code": "NOT_FOUND", "message": str(e)}, "meta": {}}), 404
    except svc.InvalidStateTransition as e:
        return jsonify({"data": None, "flash": [{"level": "warning", "message": str(e)}],
                        "error": {"code": "INVALID_STATE", "message": str(e)}, "meta": {}}), 400
    except Exception as e:
        return jsonify({"data": None, "flash": [{"level": "danger", "message": "Error al procesar la solicitud"}],
                        "error": {"code": "SERVER_ERROR", "message": str(e)}, "meta": {}}), 500


@api_permanence.post('/program/<int:program_id>/deadlines/conacyt-monthly')
@login_required
@permission_required('permanence.api.manage_deadlines', program_id_kwarg='program_id')
def api_create_conacyt_monthly_deadlines(program_id):
    """
    Crea las ventanas mensuales CONACyT del periodo activo (idempotente).
    Body opcional: {academic_period_id: int}
    """
    from app.models.academic_period import AcademicPeriod
    data = request.get_json() or {}
    academic_period_id = data.get('academic_period_id')

    if not academic_period_id:
        period = AcademicPeriod.get_active_period()
        if not period:
            return jsonify({
                "data": None,
                "flash": [{"level": "danger", "message": "No hay periodo académico activo"}],
                "error": {"code": "NO_ACTIVE_PERIOD", "message": "No hay periodo académico activo"},
                "meta": {}
            }), 400
        academic_period_id = period.id

    try:
        result = svc.create_monthly_conacyt_deadlines(
            program_id=program_id,
            academic_period_id=academic_period_id,
            coordinator_id=current_user.id,
        )
        created = result['created']
        skipped = result['skipped']
        if created == 0:
            msg = f"Todas las ventanas CONACyT ya existen para este periodo ({skipped} omitidas)"
            level = "info"
        elif skipped > 0:
            msg = f"{created} ventana(s) creadas, {skipped} ya existían"
            level = "success"
        else:
            msg = f"{created} ventana(s) mensuales CONACyT creadas correctamente"
            level = "success"

        return jsonify({
            "data": result,
            "flash": [{"level": level, "message": msg}],
            "error": None,
            "meta": {}
        }), 201 if created > 0 else 200

    except ValueError as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "INVALID_DATA", "message": str(e)},
            "meta": {}
        }), 400
    except svc.StudentNotFound as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404
    except Exception as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al crear ventanas CONACyT"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_permanence.patch('/user-program/<int:user_program_id>/conacyt-scholarship')
@login_required
@permission_required('permanence.api.manage_students')
def api_toggle_conacyt_scholarship(user_program_id):
    """Activa o desactiva la beca CONACyT de un estudiante."""
    up = db.session.get(UserProgram, user_program_id)
    if not up:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Estudiante no encontrado"}],
            "error": {"code": "NOT_FOUND", "message": "UserProgram no encontrado"},
            "meta": {}
        }), 404

    data = request.get_json() or {}
    # Acepta valor explícito o simplemente alterna el valor actual
    if 'value' in data:
        new_value = bool(data['value'])
    else:
        new_value = not up.has_conacyt_scholarship

    up.has_conacyt_scholarship = new_value

    # Notificar al estudiante
    try:
        from app.services.notification_service import NotificationService
        label_notif = 'activada' if new_value else 'desactivada'
        NotificationService.create_notification(
            user_id=up.user_id,
            notification_type='conacyt_scholarship_changed',
            title=f'Beca CONACyT {label_notif}',
            message=f'Tu beca CONACyT ha sido {label_notif} por el coordinador. '
                    f'{"Ahora verás las ventanas de entrega CONACyT en tu panel." if new_value else "Ya no verás las ventanas CONACyT."}',
            priority='medium',
            action_url='/user/dashboard',
        )
    except Exception:
        pass

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al actualizar beca CONACyT"}],
            "error": {"code": "SERVER_ERROR", "message": "Error interno"},
            "meta": {}
        }), 500

    label = 'activada' if new_value else 'desactivada'
    return jsonify({
        "data": {"has_conacyt_scholarship": new_value},
        "flash": [{"level": "success", "message": f"Beca CONACyT {label} correctamente"}],
        "error": None,
        "meta": {}
    }), 200

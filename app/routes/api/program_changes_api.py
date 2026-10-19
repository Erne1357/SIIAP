"""
API de cambios de programa.

Dos flujos distintos conviven aquí y NO deben confundirse:

  1. Autoservicio del aspirante — `POST /analyze` y `POST /execute`.
     Los llama el propio aspirante desde el panel de admisión; no llevan
     `@permission_required` porque el rol `applicant` no tiene ningún permiso
     de `program_changes.*`. Lo que los protege es la validación de negocio de
     `ProgramTransferService.validate_transfer`: ser dueño del programa de
     origen, estar en un estado transferible y tener la convocatoria abierta.

  2. Decisión del coordinador — `PUT /requests/<id>/decision`.
     Exige `program_changes.api.decide` Y que ambos programas de la solicitud
     estén dentro del alcance del coordinador.

El autoservicio NUNCA aprueba la solicitud ni se firma como decisor: deja la
solicitud en `executed`, que es lo que de verdad ocurrió.
"""

from flask import Blueprint, request, current_app
from flask_login import login_required, current_user
from app.utils.permissions import permission_required
from app.utils.api_response import api_ok, api_error, api_not_found, api_server_error
from app.models.program_change_request import PENDING
from app.services import program_changes_service
from app.services.program_changes_service import ProgramChangesService
from app.services.program_transfer_service import (
    ProgramTransferService,
    ProgramTransferError,
    ProgramTransferNotFound,
)
from app.services import program_scope_service as scope_service

api_program_changes = Blueprint('api_program_changes', __name__, url_prefix='/api/v1/program-changes')


def _int_or_none(value):
    """Convierte a int o devuelve None (falla cerrado, sin excepciones)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _transfer_denied(exc: ProgramTransferError):
    """
    Traduce una denegación del servicio a la respuesta HTTP.

    404 cuando el objeto no existe PARA ESTE USUARIO (su inscripción de origen,
    el programa destino): un 403 confirmaría que el objeto existe.
    409 cuando el objeto existe pero su estado no admite la operación.

    """
    if isinstance(exc, ProgramTransferNotFound):
        return api_not_found(exc.message)
    return api_error("CONFLICT", exc.message, status=409)


@api_program_changes.route('', methods=['POST'])
@login_required
def create_request():
    """
    Registra una solicitud de cambio de programa del propio usuario.

    El solicitante siempre es `current_user`: no se acepta un applicant_id del
    cuerpo. Además debe ser dueño de una inscripción en el programa de origen.
    """
    data = request.get_json() or {}
    from_program_id = _int_or_none(data.get('from_program_id'))
    to_program_id = _int_or_none(data.get('to_program_id'))

    if from_program_id is None or to_program_id is None:
        return api_error("VALIDATION_ERROR",
                         "Se requieren el programa de origen y el de destino.", status=400)

    try:
        ProgramTransferService.validate_change_request(
            current_user.id, from_program_id, to_program_id
        )
    except ProgramTransferError as e:
        return _transfer_denied(e)

    req = ProgramChangesService.create_request(
        applicant_id=current_user.id,
        from_program_id=from_program_id,
        to_program_id=to_program_id,
        reason=data.get('reason')
    )

    # Registrar en el historial
    program_changes_service.record_request_history(
        current_user.id, from_program_id, to_program_id, data.get('reason', ''))

    return api_ok({"id": req.id}, status=201)


@api_program_changes.route('/requests', methods=['GET'])
@login_required
def list_requests():
    """
    Solicitudes de cambio.

    Un decisor ve las de SUS programas (origen o destino dentro de su alcance);
    el jefe de posgrado, todas; cualquier otro usuario, sólo las propias.
    """
    if current_user.has_permission('program_changes.api.decide'):
        # None significa "todos los programas" (jefe de posgrado); un conjunto
        # vacío significa "ninguno" y devuelve lista vacía. Nunca lo trates
        # como "todos".
        program_ids = scope_service.accessible_program_ids(current_user)
        items = ProgramTransferService.list_change_requests(program_ids=program_ids)
    else:
        items = ProgramTransferService.list_change_requests(applicant_id=current_user.id)

    payload = [{"id": r.id, "from_program_id": r.from_program_id, "to_program_id": r.to_program_id, "status": r.status} for r in items]
    return api_ok({"items": payload})


@api_program_changes.route('/requests/<int:req_id>/decision', methods=['PUT'])
@login_required
@permission_required('program_changes.api.decide')
def decide(req_id: int):
    """
    Decide una solicitud de cambio.

    Tener `program_changes.api.decide` dice QUÉ puede hacer el coordinador, no
    SOBRE QUIÉN: la decisión mueve documentos entre dos programas, así que
    ambos deben estar dentro de su alcance. Una solicitud fuera de alcance
    responde 404, igual que una inexistente — un 403 delataría que existe.
    """
    data = request.get_json() or {}

    try:
        req = ProgramTransferService.get_change_request(req_id)
    except ProgramTransferNotFound as e:
        return api_not_found(e.message)

    in_scope = scope_service.programs_in_scope(
        current_user, [req.from_program_id, req.to_program_id]
    )
    if {req.from_program_id, req.to_program_id} - in_scope:
        return api_not_found("La solicitud de cambio no existe.")

    if req.status != PENDING:
        return api_error("CONFLICT",
                         "Esta solicitud ya fue resuelta y no puede volver a decidirse.", status=409)

    try:
        r = ProgramChangesService.decide_request(
            request_id=req_id,
            status=data.get('status'),
            decided_by=current_user.id
        )
        return api_ok({"id": r.id, "status": r.status})
    except ValueError as e:
        return api_error("BUSINESS_ERROR", str(e), status=400)
    except Exception as e:
        return api_server_error(e, message="No se pudo procesar la decisión.",
                                context=f"program_changes.decide id={req_id}")


@api_program_changes.route('/analyze', methods=['POST'])
@login_required
def analyze_transfer():
    """
    Analiza viabilidad de cambio de programa sin ejecutarlo.
    Body: {from_program_id, to_program_id}

    Analiza SIEMPRE el proceso del propio usuario y sólo si el cambio sería
    ejecutable: así el aspirante ve la razón antes de llegar al botón de
    confirmar, en vez de descubrirla al final.
    """
    data = request.get_json() or {}
    from_id = _int_or_none(data.get('from_program_id'))
    to_id = _int_or_none(data.get('to_program_id'))

    if from_id is None or to_id is None:
        return api_error("VALIDATION_ERROR",
                         "Se requieren el programa de origen y el de destino.", status=400)

    try:
        ProgramTransferService.validate_transfer(current_user.id, from_id, to_id)
    except ProgramTransferError as e:
        return _transfer_denied(e)

    try:
        analysis = ProgramTransferService.analyze_transfer(
            current_user.id,
            from_id,
            to_id
        )
        return api_ok({"analysis": analysis})
    except Exception as e:
        return api_server_error(e, message="No se pudo analizar el cambio de programa.",
                                context="program_changes.analyze_transfer")


@api_program_changes.route('/execute', methods=['POST'])
@login_required
def execute_transfer():
    """
    Ejecuta el cambio de programa del propio usuario.
    Body: {from_program_id, to_program_id, reason}
    """
    data = request.get_json() or {}
    from_id = _int_or_none(data.get('from_program_id'))
    to_id = _int_or_none(data.get('to_program_id'))
    reason = data.get('reason', '')

    if from_id is None or to_id is None:
        return api_error("VALIDATION_ERROR",
                         "Se requieren el programa de origen y el de destino.", status=400)

    # Validar ANTES de crear la solicitud: un cambio denegado no debe dejar
    # basura en program_change_request.
    try:
        ProgramTransferService.validate_transfer(current_user.id, from_id, to_id)
    except ProgramTransferError as e:
        return _transfer_denied(e)

    # Crear el request (para auditoría). Queda 'pending' hasta que se ejecuta.
    change_request = ProgramChangesService.create_request(
        applicant_id=current_user.id,
        from_program_id=from_id,
        to_program_id=to_id,
        reason=reason
    )

    # Ejecutar transferencia. `validate_transfer` corre de nuevo dentro del
    # servicio (defensa en profundidad) y puede volver a denegar si algo cambió
    # entre ambas llamadas.
    try:
        result = ProgramTransferService.execute_transfer(
            current_user.id,
            from_id,
            to_id,
            change_request_id=change_request.id
        )
    except ProgramTransferError as e:
        ProgramChangesService.mark_cancelled(change_request.id)
        return _transfer_denied(e)

    if result['success']:
        # El cambio lo ejecutó el propio aspirante bajo las reglas del
        # autoservicio: NADIE lo aprobó. Marcarlo 'approved' con
        # decided_by = el propio solicitante era una firma falsa. 'executed'
        # es un estado de pleno derecho — ver ProgramChangeRequest.
        ProgramChangesService.mark_executed(change_request.id)

        # Registrar transferencia ejecutada en el historial
        program_changes_service.record_execution_history(
            current_user.id, from_id, to_id, result)

        return api_ok({
            "message": "Cambio de programa completado exitosamente",
            "result": result
        })
    else:
        current_app.logger.error(
            f"Fallo al ejecutar cambio de programa {from_id}->{to_id} "
            f"del usuario {current_user.id}: {result.get('error')}"
        )
        ProgramChangesService.mark_cancelled(change_request.id)
        return api_error("SERVER_ERROR", "No se pudo completar el cambio de programa.",
                         status=500, level="danger")

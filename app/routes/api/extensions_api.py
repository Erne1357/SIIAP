# app/routes/api/extensions_api.py - Actualizado
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services.extensions_service import ExtensionsService
from app.models import ExtensionRequest,ProgramStep, User
from app import db
from datetime import datetime

api_extensions = Blueprint('api_extensions', __name__, url_prefix='/api/v1/extensions')

@api_extensions.route('/requests', methods=['POST'])
@login_required
def create_extension_request():
    """
    Crea una solicitud de prórroga para un archivo específico.
    Ya no requiere que exista una submission previa.
    
    JSON body:
    - archive_id (int): ID del archivo para el que se solicita prórroga
    - requested_until (str): Fecha hasta cuándo se necesita (ISO format)
    - reason (str): Motivo de la solicitud
    """
    data = request.get_json() or {}
    archive_id = data.get('archive_id')
    requested_until = data.get('requested_until')
    reason = data.get('reason', '').strip()

    if not archive_id or not requested_until or not reason:
        return jsonify({
            "ok": False, 
            "error": "archive_id, requested_until y reason son requeridos"
        }), 400

    # Validar formato de fecha
    try:
        requested_until_dt = datetime.fromisoformat(requested_until.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({
            "ok": False, 
            "error": "Formato de fecha inválido. Use ISO format (YYYY-MM-DD)"
        }), 400

    # Validar que la fecha sea futura
    if requested_until_dt <= datetime.now():
        return jsonify({
            "ok": False, 
            "error": "La fecha solicitada debe ser futura"
        }), 400

    role = 'student'
    if current_user.role and current_user.role.name in ('postgraduate_admin', 'program_admin'):
        role = 'coordinator'

    try:
        er = ExtensionsService.create_request(
            user_id=current_user.id,
            archive_id=archive_id,
            requested_by=current_user.id,
            reason=reason,
            requested_until=requested_until_dt,
            role=role
        )
        
        return jsonify({
            "ok": True, 
            "id": er.id,
            "message": "Solicitud de prórroga enviada correctamente"
        }), 201
        
    except Exception as e:
        return jsonify({
            "ok": False, 
            "error": str(e)
        }), 400

@api_extensions.route('/requests', methods=['GET'])
@login_required
def list_extension_requests():
    """
    Lista solicitudes de prórroga.
    Query params:
    - user_id (int): Filtrar por usuario (solo admins)
    - archive_id (int): Filtrar por archivo
    - status (str): Filtrar por estado
    - program_id (int): Filtrar por programa (solo admins)
    """
    user_id = request.args.get('user_id', type=int)
    archive_id = request.args.get('archive_id', type=int)
    status = request.args.get('status')
    program_id = request.args.get('program_id', type=int)

    # Restricción de permisos
    if current_user.role.name not in ('postgraduate_admin', 'program_admin'):
        user_id = current_user.id  # Los estudiantes solo ven las suyas

    try:
        requests = ExtensionsService.list_requests(
            user_id=user_id,
            archive_id=archive_id,
            status=status,
            program_id=program_id
        )
        
        items = []
        for er in requests:
            user= User.query.filter_by(id=er.user_id).first()
            userName = f"{user.first_name} {user.last_name}" if user else "Desconocido"
            items.append({
                "id": er.id,
                "user_id": er.user_id,
                "user_name": userName,
                "archive_id": er.archive_id,
                "archive_name": er.archive.name,
                "status": er.status,
                "reason": er.reason,
                "requested_until": er.requested_until.isoformat() if er.requested_until else None,
                "granted_until": er.granted_until.isoformat() if er.granted_until else None,
                "condition_text": er.condition_text,
                "created_at": er.created_at.isoformat(),
                "decided_at": er.decided_at.isoformat() if er.decided_at else None
            })
        
        return jsonify({"ok": True, "items": items}), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api_extensions.route('/requests/<int:req_id>/decision', methods=['PUT'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def decide_extension_request(req_id: int):
    """
    Decide sobre una solicitud de prórroga.
    
    JSON body:
    - status (str): 'granted', 'rejected', o 'cancelled'
    - granted_until (str, opcional): Fecha hasta cuándo se concede (requerido si status='granted')
    - condition_text (str, opcional): Condiciones específicas
    """
    data = request.get_json() or {}
    status = data.get('status')
    granted_until = data.get('granted_until')
    condition_text = data.get('condition_text')

    if status not in ('granted', 'rejected', 'cancelled'):
        return jsonify({
            "ok": False, 
            "error": "status debe ser 'granted', 'rejected' o 'cancelled'"
        }), 400

    granted_until_dt = None
    if status == 'granted':
        if not granted_until:
            return jsonify({
                "ok": False, 
                "error": "granted_until es requerido cuando status='granted'"
            }), 400
        
        try:
            granted_until_dt = datetime.fromisoformat(granted_until.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({
                "ok": False, 
                "error": "Formato de granted_until inválido"
            }), 400

    try:
        er = ExtensionsService.decide_request(
            request_id=req_id,
            status=status,
            decided_by=current_user.id,
            granted_until=granted_until_dt,
            condition_text=condition_text
        )
        
        return jsonify({
            "ok": True, 
            "id": er.id, 
            "status": er.status,
            "message": f"Solicitud {status} correctamente"
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@api_extensions.route('/archive/<int:archive_id>/status', methods=['GET'])
@login_required
def get_archive_extension_status(archive_id: int):
    """
    Obtiene el estado de prórroga para un archivo específico del usuario actual.
    
    Retorna:
    - has_pending: bool - Si tiene solicitud pendiente
    - has_active: bool - Si tiene prórroga activa
    - effective_deadline: str - Fecha límite efectiva (si hay prórroga)
    - pending_request: object - Detalles de solicitud pendiente (si existe)
    """
    try:
        has_pending = ExtensionsService.has_pending_request(current_user.id, archive_id)
        active_extension = ExtensionsService.get_active_extension(current_user.id, archive_id)
        effective_deadline = ExtensionsService.get_effective_deadline(current_user.id, archive_id)
        
        pending_request = None
        if has_pending:
            pending_requests = ExtensionsService.list_requests(
                user_id=current_user.id, 
                archive_id=archive_id, 
                status='pending'
            )
            if pending_requests:
                pr = pending_requests[0]
                pending_request = {
                    "id": pr.id,
                    "reason": pr.reason,
                    "requested_until": pr.requested_until.isoformat(),
                    "created_at": pr.created_at.isoformat()
                }
        
        return jsonify({
            "ok": True,
            "has_pending": has_pending,
            "has_active": bool(active_extension),
            "effective_deadline": effective_deadline.isoformat() if effective_deadline else None,
            "pending_request": pending_request
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    
@api_extensions.route('/requests/for-review', methods=['GET'])
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def list_extension_requests_for_review():
    """
    Lista solicitudes con información adicional del usuario para revisión administrativa.
    Query params: user_id, status, program_id
    """
    user_id = request.args.get('user_id', type=int)
    status = request.args.get('status')
    program_id = request.args.get('program_id', type=int)

    from app.models.user import User
    
    query = db.session.query(ExtensionRequest).join(User, ExtensionRequest.user_id == User.id)
    
    if user_id:
        query = query.filter(ExtensionRequest.user_id == user_id)
    if status:
        query = query.filter(ExtensionRequest.status == status)
    if program_id:
        query = query.join(ProgramStep).filter(ProgramStep.program_id == program_id)

    requests = query.order_by(ExtensionRequest.created_at.desc()).all()
    
    items = []
    for er in requests:
        user = db.session.get(User, er.user_id)
        items.append({
            "id": er.id,
            "user_id": er.user_id,
            "user_name": f"{user.first_name} {user.last_name}" if user else None,
            "user_email": user.email if user else None,
            "archive_id": er.archive_id,
            "archive_name": er.archive.name if er.archive else None,
            "status": er.status,
            "reason": er.reason,
            "requested_until": er.requested_until.isoformat() if er.requested_until else None,
            "granted_until": er.granted_until.isoformat() if er.granted_until else None,
            "condition_text": er.condition_text,
            "created_at": er.created_at.isoformat(),
            "decided_at": er.decided_at.isoformat() if er.decided_at else None
        })
    
    return jsonify({"ok": True, "items": items}), 200
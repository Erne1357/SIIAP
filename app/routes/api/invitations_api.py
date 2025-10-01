# app/routes/api/invitations_api.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services.events_service import EventsService
from app.models.event import Event
from app.models.program import Program
from app import db

api_invitations = Blueprint('api_invitations', __name__, url_prefix='/api/v1/invitations')


@api_invitations.route('/event/<int:event_id>/invite', methods=['POST'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def invite_students(event_id: int):
    """Invitar estudiantes a un evento"""
    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({"ok": False, "error": "Evento no encontrado"}), 404
    
    # Verificar permisos
    if current_user.role.name == 'program_admin':
        if event.program_id:
            program = db.session.get(Program, event.program_id)
            if not program or program.coordinator_id != current_user.id:
                return jsonify({"ok": False, "error": "Sin permisos"}), 403
    
    data = request.get_json() or {}
    user_ids = data.get('user_ids', [])
    notes = data.get('notes')
    
    if not user_ids or not isinstance(user_ids, list):
        return jsonify({"ok": False, "error": "user_ids debe ser una lista"}), 400
    
    try:
        results = EventsService.invite_students(
            event_id=event_id,
            user_ids=user_ids,
            invited_by=current_user.id,
            notes=notes
        )
        
        return jsonify({
            "ok": True,
            "invited": len(results['invited']),
            "already_invited": len(results['already_invited']),
            "already_registered": len(results['already_registered']),
            "details": results
        }), 201
        
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@api_invitations.route('/event/<int:event_id>/list', methods=['GET'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def list_event_invitations(event_id: int):
    """Listar invitaciones de un evento"""
    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({"ok": False, "error": "Evento no encontrado"}), 404
    
    # Verificar permisos
    if current_user.role.name == 'program_admin':
        if event.program_id:
            program = db.session.get(Program, event.program_id)
            if not program or program.coordinator_id != current_user.id:
                return jsonify({"ok": False, "error": "Sin permisos"}), 403
    
    try:
        invitations = EventsService.get_event_invitations(event_id)
        
        return jsonify({
            "ok": True,
            "invitations": invitations,
            "total": len(invitations)
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@api_invitations.route('/<int:invitation_id>/respond', methods=['POST'])
@login_required
def respond_to_invitation(invitation_id: int):
    """Responder a una invitación (estudiante)"""
    data = request.get_json() or {}
    accept = data.get('accept', False)
    
    try:
        invitation = EventsService.respond_to_invitation(
            invitation_id=invitation_id,
            user_id=current_user.id,
            accept=accept
        )
        
        return jsonify({
            "ok": True,
            "status": invitation.status,
            "message": "Invitación aceptada" if accept else "Invitación rechazada"
        }), 200
        
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@api_invitations.route('/my-invitations', methods=['GET'])
@login_required
def my_invitations():
    """Obtener mis invitaciones pendientes"""
    try:
        invitations = EventsService.get_my_invitations(current_user.id)
        
        return jsonify({
            "ok": True,
            "invitations": invitations,
            "total": len(invitations)
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@api_invitations.route('/<int:invitation_id>', methods=['DELETE'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def cancel_invitation(invitation_id: int):
    """Cancelar una invitación"""
    try:
        EventsService.cancel_invitation(invitation_id)
        
        return jsonify({
            "ok": True,
            "message": "Invitación cancelada"
        }), 200
        
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@api_invitations.route('/event/<int:event_id>/dates', methods=['PUT'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def update_event_dates(event_id: int):
    """Actualizar fechas del evento"""
    from datetime import datetime
    
    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({"ok": False, "error": "Evento no encontrado"}), 404
    
    # Verificar permisos
    if current_user.role.name == 'program_admin':
        if event.program_id:
            program = db.session.get(Program, event.program_id)
            if not program or program.coordinator_id != current_user.id:
                return jsonify({"ok": False, "error": "Sin permisos"}), 403
    
    data = request.get_json() or {}
    
    event_date = None
    event_end_date = None
    
    if data.get('event_date'):
        event_date = datetime.fromisoformat(data['event_date'].replace('Z', '+00:00'))
    
    if data.get('event_end_date'):
        event_end_date = datetime.fromisoformat(data['event_end_date'].replace('Z', '+00:00'))
    
    try:
        updated_event = EventsService.update_event_dates(
            event_id=event_id,
            event_date=event_date,
            event_end_date=event_end_date
        )
        
        return jsonify({
            "ok": True,
            "event_date": updated_event.event_date.isoformat() if updated_event.event_date else None,
            "event_end_date": updated_event.event_end_date.isoformat() if updated_event.event_end_date else None
        }), 200
        
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
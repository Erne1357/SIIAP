from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.services.notification_service import NotificationService
from app.models.event import EventInvitation
from app.models.event import EventAttendance
from app import db

api_notifications = Blueprint('api_notifications', __name__, url_prefix='/api/v1/notifications')


@api_notifications.get('/')
@login_required
def get_notifications():
    """
    Obtiene las notificaciones del usuario actual.
    Query params:
        - unread_only: bool (default: false)
        - limit: int (default: 50, max: 100)
        - offset: int (default: 0)
    """
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    
    notifications, total = NotificationService.get_user_notifications(
        user_id=current_user.id,
        include_read=not unread_only,
        limit=limit,
        offset=offset
    )
    
    return jsonify({
        'data': {
            'notifications': [n.to_dict() for n in notifications],
            'total': total,
            'unread_count': NotificationService.get_unread_count(current_user.id)
        },
        'meta': {
            'limit': limit,
            'offset': offset
        }
    }), 200


@api_notifications.get('/unread-count')
@login_required
def get_unread_count():
    """Obtiene solo el contador de notificaciones no leídas"""
    count = NotificationService.get_unread_count(current_user.id)
    
    return jsonify({
        'data': {
            'count': count
        }
    }), 200


@api_notifications.patch('/<int:notification_id>/read')
@login_required
def mark_notification_read(notification_id):
    """Marca una notificación como leída"""
    notification = NotificationService.mark_as_read(notification_id, current_user.id)
    
    if not notification:
        return jsonify({
            'data': None,
            'flash': [{
                'level': 'error',
                'message': 'Notificación no encontrada'
            }]
        }), 404
    
    db.session.commit()
    
    return jsonify({
        'data': notification.to_dict(),
        'flash': []
    }), 200


@api_notifications.post('/mark-all-read')
@login_required
def mark_all_notifications_read():
    """Marca todas las notificaciones como leídas"""
    count = NotificationService.mark_all_as_read(current_user.id)
    db.session.commit()
    
    return jsonify({
        'data': {
            'marked_count': count
        },
        'flash': [{
            'level': 'success',
            'message': f'{count} notificaciones marcadas como leídas'
        }]
    }), 200


@api_notifications.delete('/<int:notification_id>')
@login_required
def delete_notification(notification_id):
    """Elimina (soft delete) una notificación"""
    notification = NotificationService.delete_notification(notification_id, current_user.id)
    
    if not notification:
        return jsonify({
            'data': None,
            'flash': [{
                'level': 'error',
                'message': 'Notificación no encontrada'
            }]
        }), 404
    
    db.session.commit()
    
    return jsonify({
        'data': None,
        'flash': [{
            'level': 'success',
            'message': 'Notificación eliminada'
        }]
    }), 200


@api_notifications.post('/clear-read')
@login_required
def clear_read_notifications():
    """Elimina todas las notificaciones leídas"""
    count = NotificationService.clear_read_notifications(current_user.id)
    db.session.commit()
    
    return jsonify({
        'data': {
            'deleted_count': count
        },
        'flash': [{
            'level': 'success',
            'message': f'{count} notificaciones eliminadas'
        }]
    }), 200


@api_notifications.post('/<int:notification_id>/respond-invitation')
@login_required
def respond_invitation(notification_id):
    """
    Responde a una invitación desde una notificación.
    Body: { "response": "accepted" | "rejected" }
    """
    data = request.get_json()
    response_type = data.get('response')
    
    if response_type not in ['accepted', 'rejected']:
        return jsonify({
            'data': None,
            'flash': [{
                'level': 'error',
                'message': 'Respuesta inválida'
            }]
        }), 400
    
    # Obtener notificación
    from app.models.notification import Notification
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first()
    
    if not notification or not notification.related_invitation_id:
        return jsonify({
            'data': None,
            'flash': [{
                'level': 'error',
                'message': 'Notificación o invitación no encontrada'
            }]
        }), 404
    
    # Obtener invitación
    invitation = EventInvitation.query.get(notification.related_invitation_id)
    
    if not invitation:
        return jsonify({
            'data': None,
            'flash': [{
                'level': 'error',
                'message': 'Invitación no encontrada'
            }]
        }), 404
    
    # Actualizar invitación
    invitation.status = response_type
    invitation.responded_at = db.func.now()
    
    # Si acepta, crear registro de asistencia
    if response_type == 'accepted':
        attendance = EventAttendance(
            event_id=invitation.event_id,
            user_id=current_user.id,
            status='registered'
        )
        db.session.add(attendance)
    
    # Marcar notificación como leída
    notification.is_read = True
    notification.read_at = db.func.now()
    
    db.session.commit()
    
    message = 'Invitación aceptada' if response_type == 'accepted' else 'Invitación rechazada'
    
    return jsonify({
        'data': {
            'invitation_status': response_type
        },
        'flash': [{
            'level': 'success',
            'message': message
        }]
    }), 200
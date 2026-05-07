from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.utils.permissions import permission_required, any_permission_required
from app.services.appointments_service import AppointmentsService
from app.services.user_history_service import UserHistoryService
from app.models.appointment import Appointment
from app import db

api_appointments = Blueprint('api_appointments', __name__, url_prefix='/api/v1/appointments')

@api_appointments.route('', methods=['POST'])
@login_required
@any_permission_required('appointments.api.assign', 'appointments.api.book')
def assign():
    data = request.get_json() or {}
    try:
        appt = AppointmentsService.assign_slot(
            event_id=int(data['event_id']),
            slot_id=int(data['slot_id']),
            applicant_id=int(data['applicant_id']),
            assigned_by=current_user.id,
            notes=data.get('notes')
        )
        
        # Registrar en el historial Y enviar notificación
        try:
            from app.models.event import Event, EventSlot, EventWindow
            from app.services.notification_service import NotificationService
            slot = EventSlot.query.get(int(data['slot_id']))
            if slot:
                window = EventWindow.query.get(slot.event_window_id)
                if window:
                    event = Event.query.get(window.event_id)
                    if event:
                        # Registrar en historial
                        UserHistoryService.log_appointment_assignment(
                            user_id=int(data['applicant_id']),
                            event_title=event.title,
                            appointment_datetime=slot.starts_at.isoformat(),
                            assigned_by_admin=current_user.id
                        )
                        
                        # NUEVO: Enviar notificación con correo
                        NotificationService.notify_appointment_assigned(
                            user_id=int(data['applicant_id']),
                            event_title=event.title,
                            appointment_id=appt.id,
                            slot_datetime=slot.starts_at.strftime('%d/%m/%Y a las %H:%M'),
                            event_id=event.id,
                            location=event.location
                        )
                        
                        db.session.commit()
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error al registrar asignación de cita en historial: {e}")
        
        # Broadcast a coordinadores
        try:
            from app.extensions import socketio
            socketio.emit(
                'appointment:changed',
                {
                    'action': 'booked',
                    'appointment_id': appt.id,
                    'event_id': appt.event_id,
                    'slot_id': appt.slot_id,
                    'applicant_id': appt.applicant_id,
                },
                room='role:coordinator',
            )
        except Exception:
            pass

        return jsonify({"ok": True, "id": appt.id}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@api_appointments.route('/mine', methods=['GET'])
@login_required
@permission_required('appointments.api.list_own')
def my_appointments():
    # listado simple; ajusta filtros si quieres por evento
    appts = Appointment.query.filter_by(applicant_id=current_user.id).all()
    payload = [{
        "id": a.id,
        "event_id": a.event_id,
        "slot_id": a.slot_id,
        "status": a.status
    } for a in appts]
    return jsonify({"ok": True, "items": payload}), 200

@api_appointments.route('/<int:appointment_id>', methods=['DELETE'])
@login_required
@permission_required('appointments.api.cancel')
def cancel(appointment_id:int):
    try:
        # Obtener información antes de cancelar
        appt = Appointment.query.get(appointment_id)
        event_title = "Desconocido"
        if appt:
            from app.models.event import Event, EventSlot, EventWindow
            slot = EventSlot.query.get(appt.slot_id)
            if slot:
                window = EventWindow.query.get(slot.event_window_id)
                if window:
                    event = Event.query.get(window.event_id)
                    if event:
                        event_title = event.title
        
        appt = AppointmentsService.cancel_appointment(appointment_id, reason=request.args.get('reason'))
        
        # Registrar en el historial (incluye notificación automática)
        try:
            cancelled_by_admin = (current_user.id != appt.applicant_id)
            reason = request.args.get('reason', 'Cancelada por el usuario')
            
            UserHistoryService.log_appointment_cancellation(
                user_id=appt.applicant_id,
                event_title=event_title,
                reason=reason,
                cancelled_by_admin=cancelled_by_admin,
                admin_id=current_user.id if cancelled_by_admin else None
            )
            
            db.session.commit()
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error al registrar cancelación de cita en historial: {e}")
        
        # Broadcast a coordinadores
        try:
            from app.extensions import socketio
            socketio.emit(
                'appointment:changed',
                {
                    'action': 'cancelled',
                    'appointment_id': appt.id,
                    'event_id': appt.event_id,
                    'slot_id': appt.slot_id,
                    'applicant_id': appt.applicant_id,
                },
                room='role:coordinator',
            )
        except Exception:
            pass

        return jsonify({"ok": True, "id": appt.id, "status": appt.status}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@api_appointments.route('/<int:appointment_id>/change-requests', methods=['POST'])
@login_required
@permission_required('appointments.api.change_request')
def request_change(appointment_id:int):
    data = request.get_json() or {}
    try:
        acr = AppointmentsService.request_change(
            appointment_id=appointment_id,
            requested_by=current_user.id,
            reason=data.get('reason'),
            suggestions=data.get('suggestions')
        )
        # Broadcast a coordinadores
        try:
            from app.extensions import socketio
            socketio.emit(
                'appointment:change_requested',
                {
                    'change_request_id': acr.id,
                    'appointment_id': appointment_id,
                    'requested_by': current_user.id,
                },
                room='role:coordinator',
            )
        except Exception:
            pass
        return jsonify({"ok": True, "id": acr.id}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@api_appointments.route('/<int:appointment_id>/details', methods=['GET'])
@login_required
def appointment_details(appointment_id: int):
    """Obtiene detalles completos de una cita incluyendo slot, window y evento"""
    from app.models.event import Event, EventSlot, EventWindow
    from app.models.user import User
    
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        return jsonify({"ok": False, "error": "Cita no encontrada"}), 404
    
    # Verificar permisos
    if current_user.id != appt.applicant_id and not current_user.has_permission('appointments.api.assign'):
        return jsonify({"ok": False, "error": "No tienes permiso para ver esta cita"}), 403
    
    # Obtener relaciones
    slot = db.session.get(EventSlot, appt.slot_id)
    if not slot:
        return jsonify({"ok": False, "error": "Slot no encontrado"}), 404
        
    window = db.session.get(EventWindow, slot.event_window_id)
    if not window:
        return jsonify({"ok": False, "error": "Window no encontrada"}), 404
        
    event = db.session.get(Event, window.event_id)
    if not event:
        return jsonify({"ok": False, "error": "Evento no encontrado"}), 404
    
    # Información del coordinador que asignó
    assigner = db.session.get(User, appt.assigned_by) if appt.assigned_by else None
    
    return jsonify({
        "ok": True,
        "appointment": {
            "id": appt.id,
            "status": appt.status,
            "notes": appt.notes,
            "created_at": appt.created_at.isoformat(),
            "slot": {
                "id": slot.id,
                "starts_at": slot.starts_at.isoformat(),
                "ends_at": slot.ends_at.isoformat(),
                "status": slot.status
            },
            "event": {
                "id": event.id,
                "title": event.title,
                "type": event.type,
                "location": event.location,
                "description": event.description
            },
            "assigned_by": {
                "id": assigner.id,
                "name": f"{assigner.first_name} {assigner.last_name}"
            } if assigner else None
        }
    }), 200

@api_appointments.route('/mine/active', methods=['GET'])
@login_required
def my_active_appointments():
    """Obtiene todas las citas activas del usuario actual con detalles completos"""
    from app.models.event import Event, EventSlot, EventWindow
    
    appointments = Appointment.query.filter_by(
        applicant_id=current_user.id,
        status='scheduled'
    ).all()
    
    items = []
    for appt in appointments:
        slot = db.session.get(EventSlot, appt.slot_id)
        if not slot:
            continue
            
        window = db.session.get(EventWindow, slot.event_window_id)
        if not window:
            continue
            
        event = db.session.get(Event, window.event_id)
        if not event:
            continue
        
        # Verificar si hay solicitud de cambio pendiente
        from app.models.appointment import AppointmentChangeRequest
        pending_change = AppointmentChangeRequest.query.filter_by(
            appointment_id=appt.id,
            status='pending'
        ).first()

        items.append({
            "id": appt.id,
            "status": appt.status,
            "notes": appt.notes,
            "event_type": event.type,
            "event_title": event.title,
            "location": event.location,
            "starts_at": slot.starts_at.isoformat(),
            "ends_at": slot.ends_at.isoformat(),
            "created_at": appt.created_at.isoformat(),
            "pending_change_request": {
                "id": pending_change.id,
                "reason": pending_change.reason,
                "suggestions": pending_change.suggestions,
                "created_at": pending_change.created_at.isoformat()
            } if pending_change else None
        })
    
    return jsonify({"ok": True, "appointments": items}), 200

@api_appointments.route('/change-requests/by-event/<int:event_id>', methods=['GET'])
@login_required
@permission_required('appointments.api.assign')
def get_change_requests_by_event(event_id: int):
    """Lista solicitudes de cambio de cita pendientes para un evento específico"""
    from app.models.event import Event, EventSlot, EventWindow
    from app.models.user import User
    from app.models.appointment import AppointmentChangeRequest
    from app.models.program import Program
    from sqlalchemy import select

    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({"ok": False, "error": "Evento no encontrado"}), 404

    accessible_pids = current_user.get_accessible_program_ids()
    if accessible_pids is not None and event.program_id and event.program_id not in accessible_pids:
        return jsonify({"ok": False, "error": "Sin permisos"}), 403

    try:
        results = db.session.execute(
            select(AppointmentChangeRequest, Appointment, EventSlot, User)
            .join(Appointment, AppointmentChangeRequest.appointment_id == Appointment.id)
            .join(EventSlot, Appointment.slot_id == EventSlot.id)
            .join(User, Appointment.applicant_id == User.id)
            .where(
                Appointment.event_id == event_id,
                AppointmentChangeRequest.status == 'pending'
            )
            .order_by(AppointmentChangeRequest.created_at.desc())
        ).all()

        items = []
        for req, appt, slot, user in results:
            items.append({
                "id": req.id,
                "appointment_id": appt.id,
                "student": {
                    "id": user.id,
                    "full_name": f"{user.first_name} {user.last_name}",
                    "email": user.email
                },
                "current_slot": {
                    "id": slot.id,
                    "starts_at": slot.starts_at.isoformat(),
                    "ends_at": slot.ends_at.isoformat()
                },
                "reason": req.reason,
                "suggestions": req.suggestions,
                "created_at": req.created_at.isoformat()
            })

        return jsonify({"ok": True, "change_requests": items, "count": len(items)}), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@api_appointments.route('/change-requests/<int:req_id>/decision', methods=['PUT'])
@login_required
@permission_required('appointments.api.assign')
def decide_change(req_id:int):
    data = request.get_json() or {}
    try:
        acr = AppointmentsService.decide_change(
            request_id=req_id,
            status=data.get('status'),
            decided_by=current_user.id,
            new_slot_id=data.get('new_slot_id')
        )

        # Enviar notificación y correo al aspirante
        try:
            from app.models.event import Event, EventSlot, EventWindow
            from app.services.notification_service import NotificationService

            appt = db.session.get(Appointment, acr.appointment_id)
            slot = db.session.get(EventSlot, appt.slot_id)
            window = db.session.get(EventWindow, slot.event_window_id)
            event = db.session.get(Event, window.event_id)

            new_slot_str = slot.starts_at.strftime('%d/%m/%Y %H:%M') if slot else ''
            location = getattr(event, 'location', None)

            if acr.status == 'accepted':
                NotificationService.notify_appointment_reassigned(
                    user_id=appt.applicant_id,
                    event_title=event.title,
                    appointment_id=appt.id,
                    new_slot_datetime=new_slot_str,
                    old_slot_datetime='',
                    event_id=event.id,
                    location=location
                )
            elif acr.status == 'rejected':
                NotificationService.create_notification(
                    user_id=appt.applicant_id,
                    notification_type='appointment_change_rejected',
                    title='Cambio de horario rechazado',
                    message=f'Tu solicitud de cambio de horario para "{event.title}" fue rechazada. Tu cita original se mantiene el {new_slot_str}.',
                    priority='medium',
                    data={'event_id': event.id, 'event_title': event.title, 'slot_datetime': new_slot_str}
                )
        except Exception as notify_err:
            import logging
            logging.error(f"Error enviando notificación de cambio de cita: {notify_err}")

        return jsonify({"ok": True, "id": acr.id, "status": acr.status}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@api_appointments.route('/by-slot/<int:slot_id>', methods=['GET'])
@login_required
def get_appointment_by_slot(slot_id: int):
    """Obtiene la cita asignada a un slot específico"""
    appointment = Appointment.query.filter_by(slot_id=slot_id).first()
    
    if not appointment:
        return jsonify({"ok": True, "appointment": None}), 200
    
    # Obtener datos del estudiante
    from app.models.user import User
    student = db.session.get(User, appointment.applicant_id)
    
    return jsonify({
        "ok": True,
        "appointment": {
            "id": appointment.id,
            "status": appointment.status,
            "notes": appointment.notes,
            "student": {
                "id": student.id,
                "full_name": f"{student.first_name} {student.last_name}",
                "email": student.email
            } if student else None,
            "assigned_by": appointment.assigned_by,
            "created_at": appointment.created_at.isoformat()
        }
    }), 200

@api_appointments.route('/<int:appointment_id>/mark-status', methods=['POST'])
@login_required
@permission_required('appointments.api.assign')
def mark_appointment_status(appointment_id: int):
    """
    Marca el estado de una cita (done, no_show).
    Si se marca como 'done' y es una entrevista, actualiza admission_status.
    """
    from app.models.program import Program
    from app.models.event import EventSlot, EventWindow, Event
    from app.models import UserProgram

    data = request.get_json() or {}
    new_status = data.get('status')
    notes = data.get('notes')

    if new_status not in ['done', 'no_show']:
        return jsonify({
            "ok": False,
            "error": "Estado invalido. Usar 'done' o 'no_show'"
        }), 400

    try:
        appt = db.session.get(Appointment, appointment_id)
        if not appt:
            return jsonify({"ok": False, "error": "Cita no encontrada"}), 404

        # Verificar permisos
        slot = db.session.get(EventSlot, appt.slot_id)
        if not slot:
            return jsonify({"ok": False, "error": "Slot no encontrado"}), 404

        window = db.session.get(EventWindow, slot.event_window_id)
        event = db.session.get(Event, window.event_id)

        accessible_pids = current_user.get_accessible_program_ids()
        if accessible_pids is not None and event.program_id and event.program_id not in accessible_pids:
            return jsonify({"ok": False, "error": "Sin permisos"}), 403

        # Actualizar estado de la cita
        appt.status = new_status
        if notes:
            appt.notes = f"{appt.notes or ''}\n[{new_status.upper()}]: {notes}".strip()

        # Si es entrevista y se marca como 'done', actualizar admission_status
        if new_status == 'done' and event.type == 'interview' and event.program_id:
            user_program = UserProgram.query.filter_by(
                user_id=appt.applicant_id,
                program_id=event.program_id
            ).first()

            if user_program and user_program.admission_status == 'in_progress':
                user_program.admission_status = 'interview_completed'

                # Registrar en historial
                UserHistoryService.log_action(
                    user_id=appt.applicant_id,
                    admin_id=current_user.id,
                    action='interview_completed',
                    details=f'Entrevista completada: {event.title}'
                )

        db.session.commit()

        return jsonify({
            "ok": True,
            "flash": [{"level": "success", "message": f"Cita marcada como {new_status}"}],
            "id": appointment_id,
            "status": new_status
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@api_appointments.route('/<int:appointment_id>/cancel', methods=['POST'])
@login_required
@permission_required('appointments.api.assign')
def cancel_appointment_by_coordinator(appointment_id: int):
    """Cancelar cita desde el coordinador con motivo"""
    from app.models.program import Program
    
    data = request.get_json() or {}
    reason = data.get('reason', 'Cancelada por coordinador')
    
    try:
        appt = db.session.get(Appointment, appointment_id)
        if not appt:
            return jsonify({"ok": False, "error": "Cita no encontrada"}), 404
        
        # Verificar permisos
        from app.models.event import EventSlot, EventWindow, Event
        slot = db.session.get(EventSlot, appt.slot_id)
        if not slot:
            return jsonify({"ok": False, "error": "Slot no encontrado"}), 404
            
        window = db.session.get(EventWindow, slot.event_window_id)
        event = db.session.get(Event, window.event_id)
        
        accessible_pids = current_user.get_accessible_program_ids()
        if accessible_pids is not None and event.program_id and event.program_id not in accessible_pids:
            return jsonify({"ok": False, "error": "Sin permisos"}), 403

        # Cancelar
        appt.status = 'cancelled'
        appt.notes = f"{appt.notes or ''}\n[Cancelada]: {reason}".strip()
        slot.status = 'free'
        slot.held_by = None
        slot.hold_expires_at = None
        
        # NUEVO: Registrar en historial (incluye notificación automática)
        try:
            UserHistoryService.log_appointment_cancellation(
                user_id=appt.applicant_id,
                event_title=event.title,
                reason=reason,
                cancelled_by_admin=True,
                admin_id=current_user.id
            )
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error al registrar cancelación: {e}")
        
        db.session.commit()

        # Broadcast a coordinadores
        try:
            from app.extensions import socketio
            socketio.emit(
                'appointment:changed',
                {
                    'action': 'cancelled',
                    'appointment_id': appt.id,
                    'event_id': appt.event_id,
                    'slot_id': appt.slot_id,
                    'applicant_id': appt.applicant_id,
                    'cancelled_by_coordinator': True,
                },
                room='role:coordinator',
            )
        except Exception:
            pass

        return jsonify({"ok": True, "id": appointment_id}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
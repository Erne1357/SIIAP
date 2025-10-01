from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services.appointments_service import AppointmentsService
from app.models.appointment import Appointment
from app import db

api_appointments = Blueprint('api_appointments', __name__, url_prefix='/api/v1/appointments')

@api_appointments.route('', methods=['POST'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
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
        return jsonify({"ok": True, "id": appt.id}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@api_appointments.route('/mine', methods=['GET'])
@login_required
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
def cancel(appointment_id:int):
    try:
        appt = AppointmentsService.cancel_appointment(appointment_id, reason=request.args.get('reason'))
        return jsonify({"ok": True, "id": appt.id, "status": appt.status}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@api_appointments.route('/<int:appointment_id>/change-requests', methods=['POST'])
@login_required
def request_change(appointment_id:int):
    data = request.get_json() or {}
    try:
        acr = AppointmentsService.request_change(
            appointment_id=appointment_id,
            requested_by=current_user.id,
            reason=data.get('reason'),
            suggestions=data.get('suggestions')
        )
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
    if current_user.id != appt.applicant_id and current_user.role.name not in ('postgraduate_admin', 'program_admin'):
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
        
        items.append({
            "id": appt.id,
            "status": appt.status,
            "notes": appt.notes,
            "event_type": event.type,
            "event_title": event.title,
            "location": event.location,
            "starts_at": slot.starts_at.isoformat(),
            "ends_at": slot.ends_at.isoformat(),
            "created_at": appt.created_at.isoformat()
        })
    
    return jsonify({"ok": True, "appointments": items}), 200

@api_appointments.route('/change-requests/<int:req_id>/decision', methods=['PUT'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def decide_change(req_id:int):
    data = request.get_json() or {}
    try:
        acr = AppointmentsService.decide_change(
            request_id=req_id,
            status=data.get('status'),
            decided_by=current_user.id,
            new_slot_id=data.get('new_slot_id')
        )
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

@api_appointments.route('/<int:appointment_id>/cancel', methods=['POST'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
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
        
        if current_user.role.name == 'program_admin':
            if event.program_id:
                program = db.session.get(Program, event.program_id)
                if not program or program.coordinator_id != current_user.id:
                    return jsonify({"ok": False, "error": "Sin permisos"}), 403
        
        # Cancelar
        appt.status = 'cancelled'
        appt.notes = f"{appt.notes or ''}\n[Cancelada]: {reason}".strip()
        slot.status = 'free'
        slot.held_by = None
        slot.hold_expires_at = None
        
        db.session.commit()
        
        return jsonify({"ok": True, "id": appointment_id}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
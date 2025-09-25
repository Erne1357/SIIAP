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
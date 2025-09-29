from datetime import date, time
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services.events_service import EventsService
from app.models.event import Event, EventWindow, EventSlot
from app.models.program import Program
from app.models.appointment import Appointment
from sqlalchemy import select
from app import db
import logging

api_events = Blueprint('api_events', __name__, url_prefix='/api/v1/events')

@api_events.route('', methods=['POST'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def create_event():
    data = request.get_json() or {}
    ev = EventsService.create_event(
        program_id=data.get('program_id'),
        type_=data.get('type', 'interview'),
        title=data.get('title'),
        description=data.get('description'),
        location=data.get('location'),
        created_by=current_user.id,
        visible_to_students=bool(data.get('visible_to_students', True))
    )
    return jsonify({"ok": True, "id": ev.id}), 201

@api_events.route('/<int:event_id>/windows', methods=['POST'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def add_window(event_id:int):
    data = request.get_json() or {}
    current_app.logger.warning(f"Received add_window request with data: {data}")
    try:
        current_app.logger.warning(f"Adding window with data: {data}")
        win = EventsService.add_window(
            event_id=event_id,
            window_date=date.fromisoformat(str(data.get('date'))),
            start=time.fromisoformat(str(data.get('start_time'))),
            end=time.fromisoformat(str(data.get('end_time'))),
            slot_minutes=int(data.get('slot_minutes')),
            timezone_str=data.get('timezone','America/Ciudad_Juarez')
        )
        return jsonify({"ok": True, "id": win.id}), 201
    except Exception as e:
        current_app.logger.warning(str(e))
        return jsonify({"ok": False, "error": str(e)}), 400

@api_events.route('/windows/<int:window_id>/generate-slots', methods=['POST'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def generate_slots(window_id:int):
    try:
        slots = EventsService.generate_slots(window_id)
        return jsonify({"ok": True, "created": len(slots)}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@api_events.route('/<int:event_id>/slots', methods=['GET'])
@login_required
def list_slots(event_id:int):
    status = request.args.get('status')
    items = EventsService.list_slots(event_id=event_id, status=status)
    payload = [{"id": s.id, "starts_at": s.starts_at.isoformat(), "ends_at": s.ends_at.isoformat(), "status": s.status} for s in items]
    return jsonify({"ok": True, "items": payload}), 200

@api_events.route('', methods=['GET'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def list_events():
    """Lista eventos que el coordinador puede gestionar"""
    program_id = request.args.get('program_id', type=int)
    
    # Filtrar por programas que puede gestionar
    query = Event.query
    
    if current_user.role.name == 'program_admin':
        # Solo eventos de sus programas
        managed_programs = db.session.execute(
            select(Program.id).where(Program.coordinator_id == current_user.id)
        ).scalars().all()
        
        if not managed_programs:
            return jsonify({"ok": True, "items": []}), 200
            
        query = query.filter(Event.program_id.in_(managed_programs))
    
    if program_id:
        query = query.filter(Event.program_id == program_id)
    
    events = query.order_by(Event.created_at.desc()).all()
    
    items = []
    for event in events:
        # Contar ventanas y slots
        windows_count = EventWindow.query.filter_by(event_id=event.id).count()
        
        slots_query = db.session.query(EventSlot).join(
            EventWindow, EventWindow.id == EventSlot.event_window_id
        ).filter(EventWindow.event_id == event.id)
        
        slots_total = slots_query.count()
        slots_booked = slots_query.filter(EventSlot.status == 'booked').count()
        
        # Obtener nombre del programa
        program = db.session.get(Program, event.program_id) if event.program_id else None
        
        items.append({
            "id": event.id,
            "title": event.title,
            "type": event.type,
            "location": event.location,
            "description": event.description,
            "program_id": event.program_id,
            "program_name": program.name if program else "Todos los programas",
            "visible_to_students": event.visible_to_students,
            "windows_count": windows_count,
            "slots_total": slots_total,
            "slots_booked": slots_booked,
            "created_at": event.created_at.isoformat()
        })
    
    return jsonify({"ok": True, "items": items}), 200

@api_events.route('/<int:event_id>', methods=['DELETE'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def delete_event(event_id: int):
    """Elimina un evento y todos sus slots/appointments asociados"""
    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({"ok": False, "error": "Evento no encontrado"}), 404
    
    # Verificar permisos
    if current_user.role.name == 'program_admin':
        if not event.program_id:
            return jsonify({"ok": False, "error": "No tienes permiso para eliminar este evento"}), 403
            
        program = db.session.get(Program, event.program_id)
        if not program or program.coordinator_id != current_user.id:
            return jsonify({"ok": False, "error": "No tienes permiso para eliminar este evento"}), 403
    
    # Verificar si hay appointments activas
    appointments_count = db.session.query(Appointment).join(
        EventSlot, EventSlot.id == Appointment.slot_id
    ).join(
        EventWindow, EventWindow.id == EventSlot.event_window_id
    ).filter(
        EventWindow.event_id == event_id,
        Appointment.status == 'scheduled'
    ).count()
    
    if appointments_count > 0:
        force = request.args.get('force') in ('true', '1', 'yes')
        if not force:
            return jsonify({
                "ok": False, 
                "requires_force": True,
                "message": f"El evento tiene {appointments_count} citas activas. Usa ?force=true para eliminar."
            }), 409
    
    try:
        # Cascade debería manejar la eliminación de windows, slots y appointments
        db.session.delete(event)
        db.session.commit()
        
        return jsonify({"ok": True, "deleted": event_id}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

@api_events.route('/<int:event_id>', methods=['GET'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def get_event_details(event_id: int):
    """Obtiene detalles completos de un evento incluyendo sus ventanas"""
    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({"ok": False, "error": "Evento no encontrado"}), 404
    
    # Verificar permisos
    if current_user.role.name == 'program_admin':
        if event.program_id:
            program = db.session.get(Program, event.program_id)
            if not program or program.coordinator_id != current_user.id:
                return jsonify({"ok": False, "error": "No tienes permiso"}), 403
    
    # Obtener ventanas
    windows = EventWindow.query.filter_by(event_id=event_id).all()
    
    return jsonify({
        "ok": True,
        "id": event.id,
        "title": event.title,
        "type": event.type,
        "location": event.location,
        "description": event.description,
        "program_id": event.program_id,
        "windows": [{
            "id": w.id,
            "date": w.date.isoformat(),
            "start_time": w.start_time.isoformat(),
            "end_time": w.end_time.isoformat(),
            "slot_minutes": w.slot_minutes
        } for w in windows]
    }), 200

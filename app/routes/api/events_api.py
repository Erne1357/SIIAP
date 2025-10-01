from datetime import date, time
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services.events_service import EventsService
from app.models.event import Event, EventWindow, EventSlot
from app.models.program import Program
from app.models.appointment import Appointment
from sqlalchemy import select, or_
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
        visible_to_students=bool(data.get('visible_to_students', True)),
        capacity_type=data.get('capacity_type', 'single'),
        max_capacity=data.get('max_capacity'),
        requires_registration=bool(data.get('requires_registration', True)),
        allows_attendance_tracking=bool(data.get('allows_attendance_tracking', False)),
        status=data.get('status', 'published')
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
        # Solo eventos de sus programas O eventos globales (program_id=NULL)
        managed_programs = db.session.execute(
            select(Program.id).where(Program.coordinator_id == current_user.id)
        ).scalars().all()
        
        if not managed_programs:
            # Solo eventos globales
            query = query.filter(Event.program_id.is_(None))
        else:
            # Sus programas + eventos globales
            query = query.filter(
                or_(
                    Event.program_id.in_(managed_programs),
                    Event.program_id.is_(None)
                )
            )
    
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
            "program_name": program.name if program else None,  # CAMBIAR: Puede ser None
            "visible_to_students": event.visible_to_students,
            "capacity_type": event.capacity_type,  # AGREGAR
            "max_capacity": event.max_capacity,  # AGREGAR
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
@api_events.route('/windows/<int:window_id>', methods=['DELETE'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def delete_window(window_id: int):
    """Elimina una ventana y todos sus slots"""
    from app.services.events_service import EventsService
    
    window = db.session.get(EventWindow, window_id)
    if not window:
        return jsonify({"ok": False, "error": "Ventana no encontrada"}), 404
    
    event = db.session.get(Event, window.event_id)
    
    # Verificar permisos
    if current_user.role.name == 'program_admin':
        if event.program_id:
            program = db.session.get(Program, event.program_id)
            if not program or program.coordinator_id != current_user.id:
                return jsonify({"ok": False, "error": "Sin permisos"}), 403
    
    force = request.args.get('force') in ('true', '1', 'yes')
    
    try:
        EventsService.delete_window(window_id, force=force)
        return jsonify({"ok": True, "deleted": window_id}), 200
    except ValueError as e:
        if "force=True" in str(e):
            return jsonify({
                "ok": False,
                "requires_force": True,
                "message": str(e)
            }), 409
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@api_events.route('/slots/<int:slot_id>', methods=['DELETE'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def delete_slot(slot_id: int):
    """Elimina un slot individual"""
    from app.services.events_service import EventsService
    
    slot = db.session.get(EventSlot, slot_id)
    if not slot:
        return jsonify({"ok": False, "error": "Slot no encontrado"}), 404
    
    window = db.session.get(EventWindow, slot.event_window_id)
    event = db.session.get(Event, window.event_id)
    
    # Verificar permisos
    if current_user.role.name == 'program_admin':
        if event.program_id:
            program = db.session.get(Program, event.program_id)
            if not program or program.coordinator_id != current_user.id:
                return jsonify({"ok": False, "error": "Sin permisos"}), 403
    
    force = request.args.get('force') in ('true', '1', 'yes')
    
    try:
        EventsService.delete_slot(slot_id, force=force)
        return jsonify({"ok": True, "deleted": slot_id}), 200
    except ValueError as e:
        if "force=True" in str(e):
            return jsonify({
                "ok": False,
                "requires_force": True,
                "message": str(e)
            }), 409
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@api_events.route('/<int:event_id>/windows-list', methods=['GET'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def list_event_windows(event_id: int):
    """Lista todas las ventanas de un evento con estadísticas"""
    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({"ok": False, "error": "Evento no encontrado"}), 404
    
    # Verificar permisos
    if current_user.role.name == 'program_admin':
        if event.program_id:
            program = db.session.get(Program, event.program_id)
            if not program or program.coordinator_id != current_user.id:
                return jsonify({"ok": False, "error": "Sin permisos"}), 403
    
    windows = EventWindow.query.filter_by(event_id=event_id).order_by(
        EventWindow.date.asc(), EventWindow.start_time.asc()
    ).all()
    
    items = []
    for window in windows:
        # Contar slots
        slots_total = EventSlot.query.filter_by(event_window_id=window.id).count()
        slots_free = EventSlot.query.filter_by(
            event_window_id=window.id, status='free'
        ).count()
        slots_booked = EventSlot.query.filter_by(
            event_window_id=window.id, status='booked'
        ).count()
        
        items.append({
            "id": window.id,
            "date": window.date.isoformat(),
            "start_time": window.start_time.isoformat(),
            "end_time": window.end_time.isoformat(),
            "slot_minutes": window.slot_minutes,
            "slots_generated": window.slots_generated,
            "slots_total": slots_total,
            "slots_free": slots_free,
            "slots_booked": slots_booked
        })
    
    return jsonify({"ok": True, "windows": items}), 200

@api_events.route('/<int:event_id>', methods=['PUT'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def update_event(event_id: int):
    """Actualizar información de un evento"""
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
    
    # Campos actualizables
    if 'title' in data:
        event.title = data['title']
    if 'description' in data:
        event.description = data['description']
    if 'location' in data:
        event.location = data['location']
    if 'type' in data:
        event.type = data['type']
    if 'status' in data:
        event.status = data['status']
    if 'visible_to_students' in data:
        event.visible_to_students = data['visible_to_students']
    if 'allows_attendance_tracking' in data:
        event.allows_attendance_tracking = data['allows_attendance_tracking']
    
    # No permitir cambiar capacity_type si ya tiene registros/slots
    if 'capacity_type' in data and data['capacity_type'] != event.capacity_type:
        # Verificar si tiene slots o registros
        from app.models.event import EventAttendance
        has_slots = EventSlot.query.join(EventWindow).filter(
            EventWindow.event_id == event_id
        ).count() > 0
        has_registrations = EventAttendance.query.filter_by(event_id=event_id).count() > 0
        
        if has_slots or has_registrations:
            return jsonify({
                "ok": False,
                "error": "No se puede cambiar el tipo de capacidad de un evento con slots o registros existentes"
            }), 400
        
        event.capacity_type = data['capacity_type']
    
    if 'max_capacity' in data:
        event.max_capacity = data['max_capacity']
    
    try:
        db.session.commit()
        return jsonify({"ok": True, "id": event.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
    
@api_events.route('/public', methods=['GET'])
@login_required  
def list_public_events():
    """Lista eventos públicos visibles para estudiantes"""
    from app.models.user_program import UserProgram
    
    # Base query: eventos visibles y publicados
    query = Event.query.filter(
        Event.visible_to_students == True,
        Event.status == 'published',
        Event.capacity_type != 'single'  # Excluir eventos 1:1
    )
    
    # Si el estudiante tiene programa, mostrar:
    # 1. Eventos de su programa
    # 2. Eventos globales (program_id = NULL)
    user_program = UserProgram.query.filter_by(user_id=current_user.id).first()
    
    if user_program:
        query = query.filter(
            or_(
                Event.program_id == user_program.program_id,
                Event.program_id.is_(None)
            )
        )
    else:
        # Si no tiene programa, solo eventos globales
        query = query.filter(Event.program_id.is_(None))
    
    events = query.order_by(Event.event_date.desc().nullslast(), Event.created_at.desc()).all()
    
    items = []
    for event in events:
        # Obtener programa si existe
        program = db.session.get(Program, event.program_id) if event.program_id else None
        
        # Contar registros actuales
        from app.models.event import EventAttendance
        current_registrations = EventAttendance.query.filter_by(
            event_id=event.id,
            status='registered'
        ).count()
        
        items.append({
            "id": event.id,
            "title": event.title,
            "type": event.type,
            "description": event.description,
            "location": event.location,
            "capacity_type": event.capacity_type,
            "max_capacity": event.max_capacity,
            "current_registrations": current_registrations,
            "program_id": event.program_id,
            "program_name": program.name if program else None,
            "event_date": event.event_date.isoformat() if event.event_date else None,
            "event_end_date": event.event_end_date.isoformat() if event.event_end_date else None,
            "created_at": event.created_at.isoformat()
        })
    
    return jsonify({"ok": True, "items": items}), 200
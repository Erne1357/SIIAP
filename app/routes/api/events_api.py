from datetime import date, time
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services.events_service import EventsService

api_events = Blueprint('api_events', __name__, url_prefix='/api/v1/events')

@api_events.route('', methods=['POST'])
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'coordinator')
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
@roles_required('postgraduate_admin', 'program_admin', 'coordinator')
def add_window(event_id:int):
    data = request.get_json() or {}
    try:
        win = EventsService.add_window(
            event_id=event_id,
            window_date=date.fromisoformat(data.get('date')),
            start=time.fromisoformat(data.get('start_time')),
            end=time.fromisoformat(data.get('end_time')),
            slot_minutes=int(data.get('slot_minutes')),
            timezone_str=data.get('timezone','America/Ciudad_Juarez')
        )
        return jsonify({"ok": True, "id": win.id}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@api_events.route('/windows/<int:window_id>/generate-slots', methods=['POST'])
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'coordinator')
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

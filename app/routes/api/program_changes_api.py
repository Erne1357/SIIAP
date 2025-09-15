from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services.program_changes_service import ProgramChangesService
from app.models.program_change_request import ProgramChangeRequest

api_program_changes = Blueprint('api_program_changes', __name__, url_prefix='/api/v1/program-changes')

@api_program_changes.route('', methods=['POST'])
@login_required
def create_request():
    data = request.get_json() or {}
    req = ProgramChangesService.create_request(
        applicant_id=current_user.id,
        from_program_id=int(data['from_program_id']),
        to_program_id=int(data['to_program_id']),
        reason=data.get('reason')
    )
    return jsonify({"ok": True, "id": req.id}), 201

@api_program_changes.route('/requests', methods=['GET'])
@login_required
def list_requests():
    # simple: propios si es alumno; todos si es admin
    if current_user.role and current_user.role.name in ('postgraduate_admin','program_admin','coordinator'):
        items = ProgramChangeRequest.query.order_by(ProgramChangeRequest.created_at.desc()).all()
    else:
        items = ProgramChangeRequest.query.filter_by(applicant_id=current_user.id).order_by(ProgramChangeRequest.created_at.desc()).all()
    payload = [{"id": r.id, "from_program_id": r.from_program_id, "to_program_id": r.to_program_id, "status": r.status} for r in items]
    return jsonify({"ok": True, "items": payload}), 200

@api_program_changes.route('/requests/<int:req_id>/decision', methods=['PUT'])
@login_required
@roles_required('postgraduate_admin','program_admin','coordinator')
def decide(req_id:int):
    data = request.get_json() or {}
    try:
        r = ProgramChangesService.decide_request(
            request_id=req_id,
            status=data.get('status'),
            decided_by=current_user.id
        )
        return jsonify({"ok": True, "id": r.id, "status": r.status}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

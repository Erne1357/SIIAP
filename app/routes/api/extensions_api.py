from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services.extensions_service import ExtensionsService

api_extensions = Blueprint('api_extensions', __name__, url_prefix='/api/v1/extensions')

@api_extensions.route('/requests', methods=['POST'])
@login_required
def create_extension_request():
    data = request.get_json() or {}
    submission_id = data.get('submission_id')
    requested_until = data.get('requested_until')
    reason = data.get('reason')

    role = 'student'
    if current_user.role and current_user.role.name in ('postgraduate_admin','program_admin','coordinator','social_service'):
        # permitir también que el coordinador solicite a nombre del alumno si así lo desean
        role = 'coordinator'

    try:
        er = ExtensionsService.create_request(
            submission_id=submission_id,
            requested_by=current_user.id,
            role=role,
            reason=reason,
            requested_until=requested_until
        )
        return jsonify({"ok": True, "id": er.id}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@api_extensions.route('/requests', methods=['GET'])
@login_required
def list_extension_requests():
    submission_id = request.args.get('submission_id', type=int)
    status = request.args.get('status')
    applicant_id = request.args.get('applicant_id', type=int)

    ers = ExtensionsService.list_requests(submission_id, status, applicant_id)
    payload = [{
        "id": e.id,
        "submission_id": e.submission_id,
        "status": e.status,
        "requested_until": e.requested_until.isoformat() if e.requested_until else None,
        "granted_until": e.granted_until.isoformat() if e.granted_until else None,
        "condition_text": e.condition_text
    } for e in ers]
    return jsonify({"ok": True, "items": payload}), 200

@api_extensions.route('/requests/<int:req_id>/decision', methods=['PUT'])
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'coordinator')
def decide_extension_request(req_id:int):
    data = request.get_json() or {}
    status = data.get('status')  # granted|rejected|cancelled
    granted_until = data.get('granted_until')
    condition_text = data.get('condition_text')

    try:
        er = ExtensionsService.decide_request(
            extreq_id=req_id,
            status=status,
            decided_by=current_user.id,
            granted_until=granted_until,
            condition_text=condition_text
        )
        return jsonify({"ok": True, "id": er.id, "status": er.status}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

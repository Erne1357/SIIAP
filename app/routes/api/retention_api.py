from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.utils.auth import roles_required
from app.services.retention_service import RetentionService

api_retention = Blueprint('api_retention', __name__, url_prefix='/api/v1/retention')

@api_retention.route('/candidates', methods=['GET'])
@login_required
@roles_required('postgraduate_admin','program_admin')
def candidates():
    now = datetime.now(timezone.utc)
    items = RetentionService.compute_candidates(now)
    payload = [{"id": s.id, "archive_id": s.archive_id, "upload_date": s.upload_date.isoformat() if s.upload_date else None} for s in items]
    return jsonify({"ok": True, "count": len(items), "items": payload}), 200

@api_retention.route('/purge', methods=['POST'])
@login_required
@roles_required('postgraduate_admin','program_admin')
def purge():
    data = request.get_json() or {}
    submission_ids = data.get('submission_ids', [])
    deleted = RetentionService.purge_submissions(submission_ids)
    return jsonify({"ok": True, "deleted": deleted}), 200

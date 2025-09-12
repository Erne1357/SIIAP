# app/routes/api/admin/review_api.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app import db
from app.utils.auth import roles_required
from app.models import Submission, ProgramStep, User, Program

api_review = Blueprint("api_review", __name__, url_prefix="/api/v1/admin/review")

def _sub_to_dict(sub: Submission) -> dict:
    return {
        "id": sub.id,
        "status": sub.status,
        "upload_date": sub.upload_date.isoformat() if sub.upload_date else None,
        "review_date": sub.review_date.isoformat() if sub.review_date else None,
        "reviewer_comment": sub.reviewer_comment,
        "user": {
            "id": sub.user.id,
            "name": f"{sub.user.first_name} {sub.user.last_name}"
        } if sub.user else None,
        "program": {
            "id": sub.program_step.program.id,
            "name": sub.program_step.program.name
        } if sub.program_step and sub.program_step.program else None,
        "step": {
            "id": sub.program_step.step.id,
            "name": sub.program_step.step.name
        } if sub.program_step and sub.program_step.step else None,
        "archive": {
            "id": sub.archive.id,
            "name": sub.archive.name
        } if sub.archive else None,
    }

@api_review.get("/submissions")
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def list_submissions():
    applicant_id = request.args.get('applicant_id', type=int)
    program_id   = request.args.get('program_id',   type=int)
    status       = request.args.get('status',       'pending', type=str)
    sort         = request.args.get('sort',         'desc',    type=str)

    q = Submission.query.filter_by(status=status).join(ProgramStep)
    if applicant_id:
        q = q.filter(Submission.user_id == applicant_id)
    if program_id:
        q = q.filter(ProgramStep.program_id == program_id)

    q = q.options(
        joinedload(Submission.user),
        joinedload(Submission.program_step).joinedload(ProgramStep.program),
        joinedload(Submission.program_step).joinedload(ProgramStep.step),
        joinedload(Submission.archive),
    )
    q = q.order_by(Submission.upload_date.asc() if sort == 'asc' else Submission.upload_date.desc())
    subs = [_sub_to_dict(s) for s in q.all()]
    return jsonify({"data": {"submissions": subs}, "error": None, "meta": {}}), 200

@api_review.get("/submissions/<int:sub_id>")
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def get_submission(sub_id: int):
    sub = (
        Submission.query
        .options(
            joinedload(Submission.user),
            joinedload(Submission.program_step).joinedload(ProgramStep.program),
            joinedload(Submission.program_step).joinedload(ProgramStep.step),
            joinedload(Submission.archive),
        )
        .get_or_404(sub_id)
    )
    return jsonify({"data": {"submission": _sub_to_dict(sub)}, "error": None, "meta": {}}), 200

@api_review.post("/submissions/<int:sub_id>/decision")
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def decide_submission(sub_id: int):
    """
    JSON:
      - action: 'approve' | 'reject'
      - comment: str (optional)
    """
    sub = Submission.query.get_or_404(sub_id)
    payload = request.get_json(silent=True) or {}
    action  = (payload.get("action") or "").strip().lower()
    comment = (payload.get("comment") or "").strip()

    if action not in ("approve", "reject"):
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Acción inválida."}],
            "error": {"code": "BAD_ACTION", "message": "Acción inválida"},
            "meta": {}
        }), 400

    sub.status           = 'approved' if action == 'approve' else 'rejected'
    sub.reviewer_id      = current_user.id
    sub.review_date      = db.func.now()
    sub.reviewer_comment = comment

    db.session.commit()

    return jsonify({
        "data": {"submission": _sub_to_dict(sub)},
        "flash": [{"level": "success", "message": f"Documento {'aprobado' if action=='approve' else 'rechazado'} con éxito."}],
        "error": None, "meta": {}
    }), 200

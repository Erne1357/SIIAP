from __future__ import annotations
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select
from app import db
from app.utils.auth import roles_required
from app.models.retention_policy import RetentionPolicy
from app.models.archive import Archive
from app.models.submission import Submission
from app.services.retention_service import RetentionService
from app.services.user_history_service import UserHistoryService
from datetime import datetime, timezone

api_retention = Blueprint('api_retention', __name__, url_prefix='/api/v1/retention')

@api_retention.route('/candidates', methods=['GET'])
@login_required
@roles_required('postgraduate_admin','program_admin')
def candidates():
    now = datetime.now()
    items = RetentionService.compute_candidates(now)
    payload = [{"id": s.id, "archive_id": s.archive_id, "upload_date": s.upload_date.isoformat() if s.upload_date else None} for s in items]
    return jsonify({"ok": True, "count": len(items), "items": payload}), 200

@api_retention.route('/purge', methods=['POST'])
@login_required
@roles_required('postgraduate_admin','program_admin')
def purge():
    data = request.get_json() or {}
    submission_ids = data.get('submission_ids', [])
    
    # Obtener información de los documentos antes de eliminar para el historial
    submissions_info = []
    if submission_ids:
        submissions = db.session.execute(
            select(Submission, Archive).join(Archive, Submission.archive_id == Archive.id)
            .where(Submission.id.in_(submission_ids))
        ).all()
        
        for submission, archive in submissions:
            submissions_info.append({
                'user_id': submission.user_id,
                'archive_name': archive.name,
                'submission_id': submission.id
            })
    
    deleted = RetentionService.purge_submissions(submission_ids)
    
    # Registrar en el historial para cada usuario afectado
    for info in submissions_info:
        try:
            UserHistoryService.log_document_purged(
                user_id=info['user_id'],
                archive_name=info['archive_name'],
                reason=f"Eliminación por política de retención (ID: {info['submission_id']})",
                admin_id=current_user.id
            )
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error al registrar eliminación de documento en historial: {e}")
    
    # Commit del historial
    try:
        db.session.commit()
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error al guardar historial de eliminaciones: {e}")
    
    return jsonify({"ok": True, "deleted": deleted}), 200

@api_retention.route("/policies", methods=["GET"])
@login_required
@roles_required("postgraduate_admin", "program_admin")
def list_policies():
    rows = db.session.execute(select(RetentionPolicy)).scalars().all()
    items = [{
        "id": r.id,
        "archive_id": r.archive_id,
        "keep_years": r.keep_years,
        "keep_forever": bool(r.keep_forever),
        "apply_after": r.apply_after
    } for r in rows]
    return jsonify({"ok": True, "items": items}), 200


@api_retention.route("/policies", methods=["POST"])
@login_required
@roles_required("postgraduate_admin", "program_admin")
def create_policy():
    data = request.get_json() or {}
    archive_id = data.get("archive_id")
    keep_forever = bool(data.get("keep_forever", False))
    keep_years = data.get("keep_years")
    apply_after = data.get("apply_after") or "graduated"

    if not archive_id:
        return jsonify({"ok": False, "error": "archive_id es requerido"}), 400
    a = db.session.get(Archive, archive_id)
    if not a:
        return jsonify({"ok": False, "error": "Archivo no existe"}), 404

    # Un archivo → 1 política. Si ya hay, actualizamos (upsert simple).
    existing = db.session.execute(
        select(RetentionPolicy).where(RetentionPolicy.archive_id == archive_id)
    ).scalar_one_or_none()

    if keep_forever:
        keep_years = None
    else:
        # validar años si no es forever
        if not keep_years or int(keep_years) <= 0:
            return jsonify({"ok": False, "error": "keep_years debe ser > 0 si no es 'forever'"}), 400
        keep_years = int(keep_years)

    try:
        if existing:
            existing.keep_forever = keep_forever
            existing.keep_years = keep_years
            existing.apply_after = apply_after
            db.session.commit()
            return jsonify({"ok": True, "id": existing.id}), 200
        else:
            rp = RetentionPolicy(
                archive_id=archive_id,
                keep_forever=keep_forever,
                keep_years=keep_years,
                apply_after=apply_after
            )
            db.session.add(rp)
            db.session.commit()
            return jsonify({"ok": True, "id": rp.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400


@api_retention.route("/policies/<int:policy_id>", methods=["PUT"])
@login_required
@roles_required("postgraduate_admin", "program_admin")
def update_policy(policy_id: int):
    data = request.get_json() or {}
    keep_forever = bool(data.get("keep_forever", False))
    keep_years = data.get("keep_years")
    apply_after = data.get("apply_after") or "graduated"

    rp = db.session.get(RetentionPolicy, policy_id)
    if not rp:
        return jsonify({"ok": False, "error": "Política no encontrada"}), 404

    if keep_forever:
        keep_years = None
    else:
        if not keep_years or int(keep_years) <= 0:
            return jsonify({"ok": False, "error": "keep_years debe ser > 0 si no es 'forever'"}), 400
        keep_years = int(keep_years)

    try:
        rp.keep_forever = keep_forever
        rp.keep_years = keep_years
        rp.apply_after = apply_after
        db.session.commit()
        return jsonify({"ok": True, "id": rp.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400


@api_retention.route("/policies/<int:policy_id>", methods=["DELETE"])
@login_required
@roles_required("postgraduate_admin", "program_admin")
def delete_policy(policy_id: int):
    rp = db.session.get(RetentionPolicy, policy_id)
    if not rp:
        return jsonify({"ok": False, "error": "Política no encontrada"}), 404
    try:
        db.session.delete(rp)
        db.session.commit()
        return jsonify({"ok": True, "deleted": policy_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400

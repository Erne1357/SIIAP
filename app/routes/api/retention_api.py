from __future__ import annotations
from flask import Blueprint, request
from flask_login import login_required, current_user
from sqlalchemy import select
from app import db
from app.utils.permissions import permission_required
from app.utils.api_response import api_ok, api_error, api_not_found, api_server_error
from app.utils.validation import parse_json
from app.schemas.retention import RetentionPolicyIn
from app.models.retention_policy import RetentionPolicy
from app.models.archive import Archive
from app.models.submission import Submission
from app.services.public_id_service import uuid_for
from app.services.retention_service import RetentionService
from app.services.user_history_service import UserHistoryService
from datetime import datetime, timezone
from app.utils.datetime_utils import now_local

api_retention = Blueprint('api_retention', __name__, url_prefix='/api/v1/retention')

@api_retention.route('/candidates', methods=['GET'])
@login_required
@permission_required('admin_retention.api.manage')
def candidates():
    now = now_local()
    items = RetentionService.compute_candidates(now)
    # Identificadores públicos: la consola devuelve estos mismos valores en
    # `submission_ids` al purgar.
    payload = [{
        "id": str(s.uuid) if s.uuid else None,
        "archive_id": str(s.archive.uuid) if s.archive and s.archive.uuid else None,
        "upload_date": s.upload_date.isoformat() if s.upload_date else None,
    } for s in items]
    return api_ok({"count": len(items), "items": payload}, meta={"count": len(items)})

@api_retention.route('/purge', methods=['POST'])
@login_required
@permission_required('admin_retention.api.manage')
def purge():
    data = request.get_json() or {}
    # La consola manda los UUID públicos de las entregas; el servicio de
    # retención sigue trabajando con los ids internos.
    submission_ids = [
        row.id for row in (
            Submission.by_uuid(raw) for raw in (data.get('submission_ids') or [])
        ) if row is not None
    ]
    
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
                # Handle publico, no la clave primaria. Este valor acaba
                # interpolado en `reason`, que el historial devuelve al propio
                # estudiante, asi que republicaba el id enumerable que el
                # cambio a UUID retira de todas las demas superficies.
                'submission_ref': str(submission.uuid),
            })
    
    deleted = RetentionService.purge_submissions(submission_ids)
    
    # Registrar en el historial para cada usuario afectado
    for info in submissions_info:
        try:
            UserHistoryService.log_document_purged(
                user_id=info['user_id'],
                archive_name=info['archive_name'],
                reason=f"Eliminación por política de retención (ref: {info['submission_ref']})",
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
    
    return api_ok({"deleted": deleted})

@api_retention.route("/policies", methods=["GET"])
@login_required
@permission_required('admin_retention.api.manage')
def list_policies():
    rows = db.session.execute(select(RetentionPolicy)).scalars().all()
    items = [{
        # `id` de la política sigue siendo entero (no tiene handle público);
        # `archive_id` nombra un Archive y sale como UUID.
        "id": r.id,
        "archive_id": uuid_for(Archive, r.archive_id),
        "keep_years": r.keep_years,
        "keep_forever": bool(r.keep_forever),
        "apply_after": r.apply_after
    } for r in rows]
    return api_ok({"items": items})


@api_retention.route("/policies", methods=["POST"])
@login_required
@permission_required('admin_retention.api.manage')
def create_policy():
    payload = parse_json(RetentionPolicyIn)
    # `archive_id` llega como UUID público en el cuerpo.
    raw_archive = payload.archive_id
    if not raw_archive:
        return api_error("VALIDATION_ERROR", "Selecciona un archivo.", status=400,
                         fields={"archive_id": "Este campo es obligatorio."})
    a = Archive.by_uuid(raw_archive)
    if not a:
        return api_not_found("Archivo no existe")
    archive_id = a.id
    keep_forever = payload.keep_forever
    keep_years = payload.keep_years
    apply_after = payload.apply_after

    # Un archivo → 1 política. Si ya hay, actualizamos (upsert simple).
    existing = db.session.execute(
        select(RetentionPolicy).where(RetentionPolicy.archive_id == archive_id)
    ).scalar_one_or_none()

    try:
        if existing:
            existing.keep_forever = keep_forever
            existing.keep_years = keep_years
            existing.apply_after = apply_after
            db.session.commit()
            return api_ok({"id": existing.id})
        else:
            rp = RetentionPolicy(
                archive_id=archive_id,
                keep_forever=keep_forever,
                keep_years=keep_years,
                apply_after=apply_after
            )
            db.session.add(rp)
            db.session.commit()
            return api_ok({"id": rp.id}, status=201)
    except Exception as e:
        db.session.rollback()
        return api_server_error(e, context="retention.create_policy")


@api_retention.route("/policies/<int:policy_id>", methods=["PUT"])
@login_required
@permission_required('admin_retention.api.manage')
def update_policy(policy_id: int):
    payload = parse_json(RetentionPolicyIn)
    keep_forever = payload.keep_forever
    keep_years = payload.keep_years
    apply_after = payload.apply_after

    rp = db.session.get(RetentionPolicy, policy_id)
    if not rp:
        return api_not_found("Política no encontrada")

    try:
        rp.keep_forever = keep_forever
        rp.keep_years = keep_years
        rp.apply_after = apply_after
        db.session.commit()
        return api_ok({"id": rp.id})
    except Exception as e:
        db.session.rollback()
        return api_server_error(e, context="retention.update_policy")


@api_retention.route("/policies/<int:policy_id>", methods=["DELETE"])
@login_required
@permission_required('admin_retention.api.manage')
def delete_policy(policy_id: int):
    rp = db.session.get(RetentionPolicy, policy_id)
    if not rp:
        return api_not_found("Política no encontrada")
    try:
        db.session.delete(rp)
        db.session.commit()
        return api_ok({"deleted": policy_id})
    except Exception as e:
        db.session.rollback()
        return api_server_error(e, context="retention.delete_policy")

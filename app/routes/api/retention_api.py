from __future__ import annotations
from flask import Blueprint
from flask_login import login_required, current_user
from app.utils.permissions import permission_required
from app.utils.api_response import api_ok, api_error, api_server_error
from app.utils.validation import parse_json
from app.schemas.retention import RetentionPolicyIn, PurgeIn
from app.services import retention_service
from app.services.errors import DomainError
from app.services.retention_service import RetentionService
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
    payload = parse_json(PurgeIn)
    # La consola manda los UUID públicos de las entregas; el servicio de
    # retención sigue trabajando con los ids internos.
    deleted = retention_service.purge_with_history(payload.submission_ids, current_user.id)
    return api_ok({"deleted": deleted})

@api_retention.route("/policies", methods=["GET"])
@login_required
@permission_required('admin_retention.api.manage')
def list_policies():
    return api_ok({"items": retention_service.list_policies()})


@api_retention.route("/policies", methods=["POST"])
@login_required
@permission_required('admin_retention.api.manage')
def create_policy():
    payload = parse_json(RetentionPolicyIn)
    # `archive_id` llega como UUID público en el cuerpo.
    if not payload.archive_id:
        return api_error("VALIDATION_ERROR", "Selecciona un archivo.", status=400,
                         fields={"archive_id": "Este campo es obligatorio."})
    # Un archivo → 1 política. Si ya hay, se actualiza (upsert simple).
    try:
        policy_id, created = retention_service.upsert_policy(
            payload.archive_id, payload.keep_forever, payload.keep_years, payload.apply_after
        )
    except DomainError:
        raise
    except Exception as e:
        return api_server_error(e, context="retention.create_policy")
    return api_ok({"id": policy_id}, status=201 if created else 200)


@api_retention.route("/policies/<int:policy_id>", methods=["PUT"])
@login_required
@permission_required('admin_retention.api.manage')
def update_policy(policy_id: int):
    payload = parse_json(RetentionPolicyIn)
    try:
        updated_id = retention_service.update_policy(
            policy_id, payload.keep_forever, payload.keep_years, payload.apply_after
        )
    except DomainError:
        raise
    except Exception as e:
        return api_server_error(e, context="retention.update_policy")
    return api_ok({"id": updated_id})


@api_retention.route("/policies/<int:policy_id>", methods=["DELETE"])
@login_required
@permission_required('admin_retention.api.manage')
def delete_policy(policy_id: int):
    try:
        deleted_id = retention_service.delete_policy(policy_id)
    except DomainError:
        raise
    except Exception as e:
        return api_server_error(e, context="retention.delete_policy")
    return api_ok({"deleted": deleted_id})

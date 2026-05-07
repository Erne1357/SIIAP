# app/routes/api/admin/purge_api.py
"""
API REST para respaldo ZIP previo a purga física de archivos.

Endpoints:
  GET    /api/v1/admin/purge/candidates?category=...
  POST   /api/v1/admin/purge/start
  GET    /api/v1/admin/purge/<run_id>/archive.zip
  POST   /api/v1/admin/purge/<run_id>/confirm
  POST   /api/v1/admin/purge/<run_id>/cancel
  GET    /api/v1/admin/purge/runs

Permisos:
  admin.api.purge_view     — listar candidatos y runs
  admin.api.purge_archive  — crear/descargar/cancelar
  admin.api.purge_confirm  — confirmar purga física
"""

from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, after_this_request
from flask_login import login_required, current_user

from app.utils.permissions import permission_required
import app.services.applicant_archive_service as svc

api_purge = Blueprint('api_purge', __name__, url_prefix='/api/v1/admin/purge')


# ---------------------------------------------------------------------------
# GET /candidates
# ---------------------------------------------------------------------------

@api_purge.get('/candidates')
@login_required
@permission_required('admin.api.purge_view')
def list_candidates():
    category = request.args.get('category', type=str)
    if not category:
        return jsonify({
            "data": None,
            "error": {"code": "MISSING_FIELD", "message": "category es requerido"},
            "meta": {}
        }), 400
    try:
        items = svc.list_candidates(category)
        return jsonify({
            "data": items,
            "error": None,
            "meta": {"count": len(items), "category": category}
        }), 200
    except svc.InvalidPurgeType as e:
        return jsonify({
            "data": None,
            "error": {"code": "INVALID_CATEGORY", "message": str(e)},
            "meta": {}
        }), 400
    except Exception as e:
        return jsonify({
            "data": None,
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


# ---------------------------------------------------------------------------
# POST /start
# ---------------------------------------------------------------------------

@api_purge.post('/start')
@login_required
@permission_required('admin.api.purge_archive')
def start_purge_run():
    body = request.get_json(silent=True) or {}
    user_program_ids = body.get('user_program_ids') or []
    purge_type = body.get('purge_type')
    notes = body.get('notes')

    if not user_program_ids or not isinstance(user_program_ids, list):
        return jsonify({
            "data": None,
            "error": {"code": "MISSING_FIELD", "message": "user_program_ids es requerido (lista)"},
            "meta": {}
        }), 400
    if not purge_type:
        return jsonify({
            "data": None,
            "error": {"code": "MISSING_FIELD", "message": "purge_type es requerido"},
            "meta": {}
        }), 400

    try:
        run = svc.create_purge_run(
            user_program_ids=user_program_ids,
            purge_type=purge_type,
            initiated_by_id=current_user.id,
            notes=notes,
        )
        return jsonify({
            "data": {
                "run": run.to_dict(),
                "archive_url": f'/api/v1/admin/purge/{run.run_id}/archive.zip',
                "confirm_url": f'/api/v1/admin/purge/{run.run_id}/confirm',
                "cancel_url": f'/api/v1/admin/purge/{run.run_id}/cancel',
            },
            "flash": [{
                "level": "success",
                "message": (
                    "Respaldo generado. Descarga el ZIP y luego confirma "
                    "la purga física para borrar los archivos del servidor."
                )
            }],
            "error": None,
            "meta": {}
        }), 201
    except svc.InvalidPurgeType as e:
        return jsonify({
            "data": None,
            "error": {"code": "INVALID_PURGE_TYPE", "message": str(e)},
            "meta": {}
        }), 400
    except svc.PurgeError as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": str(e)}],
            "error": {"code": "PURGE_ERROR", "message": str(e)},
            "meta": {}
        }), 400
    except Exception as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al generar respaldo"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


# ---------------------------------------------------------------------------
# GET /<run_id>/archive.zip
# ---------------------------------------------------------------------------

@api_purge.get('/<run_id>/archive.zip')
@login_required
@permission_required('admin.api.purge_archive')
def download_archive(run_id):
    try:
        path, size, on_complete = svc.stream_archive(
            run_id=run_id,
            downloader_user_id=current_user.id,
        )
    except svc.PurgeRunNotFound as e:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404
    except svc.InvalidPurgeState as e:
        return jsonify({
            "data": None,
            "error": {"code": "INVALID_STATE", "message": str(e)},
            "meta": {}
        }), 409
    except svc.PurgeError as e:
        return jsonify({
            "data": None,
            "error": {"code": "PURGE_ERROR", "message": str(e)},
            "meta": {}
        }), 400

    @after_this_request
    def _mark_downloaded(response):
        try:
            response.call_on_close(on_complete)
        except Exception:
            pass
        return response

    return send_file(
        path,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'purge_{run_id}.zip',
        max_age=0,
        conditional=True,
    )


# ---------------------------------------------------------------------------
# POST /<run_id>/confirm
# ---------------------------------------------------------------------------

@api_purge.post('/<run_id>/confirm')
@login_required
@permission_required('admin.api.purge_confirm')
def confirm_purge(run_id):
    try:
        result = svc.confirm_purge(run_id, confirmer_user_id=current_user.id)
        return jsonify({
            "data": result,
            "flash": [{
                "level": "success",
                "message": (
                    f'Purga aplicada: {result["deleted_files"]} archivo(s) borrado(s), '
                    f'{result["purged_submissions"]} submission(s) actualizadas.'
                )
            }],
            "error": None,
            "meta": {}
        }), 200
    except svc.PurgeRunNotFound as e:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404
    except svc.InvalidPurgeState as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": str(e)}],
            "error": {"code": "INVALID_STATE", "message": str(e)},
            "meta": {}
        }), 409
    except Exception as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al ejecutar purga"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


# ---------------------------------------------------------------------------
# POST /<run_id>/cancel
# ---------------------------------------------------------------------------

@api_purge.post('/<run_id>/cancel')
@login_required
@permission_required('admin.api.purge_archive')
def cancel_run(run_id):
    try:
        svc.cancel_purge_run(run_id, canceller_user_id=current_user.id)
        return jsonify({
            "data": {"run_id": run_id, "status": "cancelled"},
            "flash": [{"level": "info", "message": "Respaldo cancelado. ZIP eliminado."}],
            "error": None,
            "meta": {}
        }), 200
    except svc.PurgeRunNotFound as e:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404
    except svc.InvalidPurgeState as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": str(e)}],
            "error": {"code": "INVALID_STATE", "message": str(e)},
            "meta": {}
        }), 409
    except Exception as e:
        return jsonify({
            "data": None,
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


# ---------------------------------------------------------------------------
# GET /runs
# ---------------------------------------------------------------------------

@api_purge.get('/runs')
@login_required
@permission_required('admin.api.purge_view')
def list_runs():
    try:
        svc.sweep_expired_runs()
        runs = svc.list_runs(limit=50)
        return jsonify({
            "data": runs,
            "error": None,
            "meta": {"count": len(runs)}
        }), 200
    except Exception as e:
        return jsonify({
            "data": None,
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500

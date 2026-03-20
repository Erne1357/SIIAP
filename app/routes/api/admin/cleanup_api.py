# app/routes/api/admin/cleanup_api.py
"""
API de limpieza de datos — endpoints de preview para el panel de administración.

La ejecución real de limpieza se delega a los Celery tasks en maintenance.py.
Estos endpoints sólo permiten previsualizar candidatos antes de ejecutar.
"""
from flask import Blueprint, jsonify
from flask_login import login_required
from app.utils.auth import roles_required

api_cleanup = Blueprint('api_cleanup', __name__, url_prefix='/api/admin/cleanup')


def _ok(data, total=None):
    payload = {'ok': True, 'data': data}
    if total is not None:
        payload['total'] = total
    return jsonify(payload)


def _err(msg, code=400):
    return jsonify({'ok': False, 'error': msg}), code


@api_cleanup.get('/expired-candidates')
@login_required
@roles_required('postgraduate_admin')
def get_expired_candidates():
    """
    Lista aspirantes que serían marcados como 'expired' en la próxima
    ejecución de cleanup_expired_admission_files.

    Útil para previsualizar el impacto antes de ejecutar la tarea manualmente.
    """
    try:
        from app.services.data_cleanup_service import DataCleanupService
        candidates = DataCleanupService.get_expired_candidates()
        return _ok(candidates, total=len(candidates))
    except Exception as e:
        return _err(str(e), 500)


@api_cleanup.get('/inactive-students')
@login_required
@roles_required('postgraduate_admin')
def get_inactive_students():
    """
    Lista estudiantes activos sin inscripción semestral confirmada
    en el período académico activo.

    Son los candidatos a ser notificados por notify_pending_permanence_docs.
    """
    try:
        from app.services.data_cleanup_service import DataCleanupService
        students = DataCleanupService.get_inactive_students()
        return _ok(students, total=len(students))
    except Exception as e:
        return _err(str(e), 500)

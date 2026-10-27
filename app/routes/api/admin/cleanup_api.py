# app/routes/api/admin/cleanup_api.py
"""
API de limpieza de datos — endpoints de preview para el panel de administración.

La ejecución real de limpieza se delega a los Celery tasks en maintenance.py.
Estos endpoints sólo permiten previsualizar candidatos antes de ejecutar.
"""
from flask import Blueprint
from flask_login import login_required
from app.utils.permissions import permission_required
from app.utils.api_response import api_ok, api_server_error

api_cleanup = Blueprint('api_cleanup', __name__, url_prefix='/api/admin/cleanup')


@api_cleanup.get('/expired-candidates')
@login_required
@permission_required('admin_cleanup.api.expired_candidates')
def get_expired_candidates():
    """
    Lista aspirantes que serían marcados como 'expired' en la próxima
    ejecución de cleanup_expired_admission_files.

    Útil para previsualizar el impacto antes de ejecutar la tarea manualmente.
    """
    try:
        from app.services.data_cleanup_service import DataCleanupService
        candidates = DataCleanupService.get_expired_candidates()
        return api_ok(candidates, meta={'total': len(candidates)})
    except Exception as e:
        return api_server_error(e, context='cleanup.get_expired_candidates')


@api_cleanup.get('/inactive-students')
@login_required
@permission_required('admin_cleanup.api.inactive_students')
def get_inactive_students():
    """
    Lista estudiantes activos sin inscripción semestral confirmada
    en el período académico activo.

    Son los candidatos a ser notificados por notify_pending_permanence_docs.
    """
    try:
        from app.services.data_cleanup_service import DataCleanupService
        students = DataCleanupService.get_inactive_students()
        return api_ok(students, meta={'total': len(students)})
    except Exception as e:
        return api_server_error(e, context='cleanup.get_inactive_students')

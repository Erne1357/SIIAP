"""
API REST para el panel de administración del worker Celery.

Endpoints:
  GET  /api/admin/worker/status              — Estado del worker (ping, tareas activas)
  GET  /api/admin/worker/tasks               — Historial de TaskLog (paginado, filtrable)
  POST /api/admin/worker/tasks/run           — Ejecutar tarea manualmente
  GET  /api/admin/worker/schedules           — Listar schedules de redbeat
  PUT  /api/admin/worker/schedules/<name>    — Actualizar schedule (cron / habilitado)
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.utils.permissions import permission_required
from app.extensions import celery as celery_app

logger = logging.getLogger(__name__)

api_celery_admin = Blueprint(
    'api_celery_admin',
    __name__,
    url_prefix='/api/admin/worker',
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ok(data=None, meta=None):
    return jsonify({'data': data, 'error': None, 'meta': meta or {}})


def _err(msg, code=400):
    return jsonify({'data': None, 'error': {'message': msg}, 'meta': {}}), code


# ─────────────────────────────────────────────────────────────────────────────
# 1. ESTADO DEL WORKER
# ─────────────────────────────────────────────────────────────────────────────

@api_celery_admin.route('/status', methods=['GET'])
@login_required
@permission_required('admin_celery.api.status')
def worker_status():
    """
    Hace ping al worker y devuelve:
      - online: bool
      - workers: lista de workers activos
      - active_tasks: lista de tareas en ejecución ahora mismo
      - reserved_tasks: tareas encoladas pendientes de ejecutar
    """
    try:
        inspect = celery_app.control.inspect(timeout=3)

        ping      = inspect.ping()       or {}
        active    = inspect.active()     or {}
        reserved  = inspect.reserved()   or {}

        workers = list(ping.keys())
        active_list   = [t for tasks in active.values()   for t in tasks]
        reserved_list = [t for tasks in reserved.values() for t in tasks]

        return _ok({
            'online':          len(workers) > 0,
            'workers':         workers,
            'active_tasks':    active_list,
            'reserved_tasks':  reserved_list,
        })
    except Exception as exc:
        logger.error(f"[celery_api] worker_status error: {exc}")
        return _ok({'online': False, 'workers': [], 'active_tasks': [], 'reserved_tasks': []})


# ─────────────────────────────────────────────────────────────────────────────
# 2. HISTORIAL DE EJECUCIONES (TaskLog)
# ─────────────────────────────────────────────────────────────────────────────

@api_celery_admin.route('/tasks', methods=['GET'])
@login_required
@permission_required('admin_celery.api.list_tasks')
def task_history():
    """
    Devuelve el historial de TaskLog paginado.

    Query params:
      page       (default 1)
      per_page   (default 20, max 100)
      status     filtrar por estado (success, failure, started, retry…)
      task_name  filtrar por nombre de tarea
      triggered_by  filtrar por 'manual' o 'scheduled'
    """
    from app.models.task_log import TaskLog

    page       = request.args.get('page', 1, type=int)
    per_page   = min(request.args.get('per_page', 20, type=int), 100)
    status     = request.args.get('status')
    task_name  = request.args.get('task_name')
    triggered  = request.args.get('triggered_by')

    q = TaskLog.query

    if status:
        q = q.filter(TaskLog.status == status)
    if task_name:
        q = q.filter(TaskLog.task_name == task_name)
    if triggered:
        q = q.filter(TaskLog.triggered_by == triggered)

    pagination = q.order_by(TaskLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return _ok(
        data=[t.to_dict() for t in pagination.items],
        meta={
            'page':       pagination.page,
            'per_page':   pagination.per_page,
            'total':      pagination.total,
            'pages':      pagination.pages,
            'has_next':   pagination.has_next,
            'has_prev':   pagination.has_prev,
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. EJECUTAR TAREA MANUALMENTE
# ─────────────────────────────────────────────────────────────────────────────

# Mapa de nombres de tareas permitidas para ejecución manual
_RUNNABLE_TASKS = {
    'cleanup_expired_admission_files':  'app.tasks.maintenance.cleanup_expired_admission_files',
    'apply_retention_policies':         'app.tasks.maintenance.apply_retention_policies',
    'cleanup_old_notifications':        'app.tasks.maintenance.cleanup_old_notifications',
    'check_deferral_expirations':       'app.tasks.maintenance.check_deferral_expirations',
    'notify_pending_permanence_docs':   'app.tasks.maintenance.notify_pending_permanence_docs',
    'send_bulk_notification_by_filter': 'app.tasks.notifications.send_bulk_notification_by_filter',
}


@api_celery_admin.route('/tasks/run', methods=['POST'])
@login_required
@permission_required('admin_celery.api.run_task')
def run_task():
    """
    Encola una tarea para ejecución inmediata.

    Body JSON:
      task_key  (str, requerido) — clave del mapa _RUNNABLE_TASKS
      kwargs    (dict, opcional) — argumentos de la tarea
    """
    from app import db
    from app.models.task_log import TaskLog

    body     = request.get_json(silent=True) or {}
    task_key = body.get('task_key', '').strip()
    kwargs   = body.get('kwargs', {})

    if task_key not in _RUNNABLE_TASKS:
        return _err(f"Tarea desconocida: '{task_key}'. Opciones: {list(_RUNNABLE_TASKS.keys())}")

    task_name = _RUNNABLE_TASKS[task_key]

    try:
        # Obtener la tarea registrada en Celery
        task_fn = celery_app.tasks.get(task_name)
        if task_fn is None:
            return _err(f"La tarea '{task_name}' no está registrada en el worker.")

        # Encolar con .apply_async para obtener el task_id
        async_result = task_fn.apply_async(kwargs=kwargs)
        task_id = async_result.id

        # Crear el TaskLog marcado como 'manual' inmediatamente
        log = TaskLog(
            task_id      = task_id,
            task_name    = task_name,
            status       = 'pending',
            triggered_by = 'manual',
            triggered_by_user_id = current_user.id,
            kwargs       = kwargs,
            created_at   = datetime.utcnow(),
        )
        db.session.add(log)
        db.session.commit()

        logger.info(
            f"[celery_api] Tarea manual encolada: {task_name} "
            f"por user {current_user.id} → task_id={task_id}"
        )

        return _ok({'task_id': task_id, 'task_name': task_name, 'status': 'pending'})

    except Exception as exc:
        logger.error(f"[celery_api] run_task error: {exc}", exc_info=True)
        return _err(f"Error al encolar la tarea: {exc}", 500)


# ─────────────────────────────────────────────────────────────────────────────
# 4. LISTAR SCHEDULES (redbeat)
# ─────────────────────────────────────────────────────────────────────────────

@api_celery_admin.route('/schedules', methods=['GET'])
@login_required
@permission_required('admin_celery.api.manage')
def list_schedules():
    """
    Lee los schedules almacenados en Redis por redbeat y los serializa.
    """
    try:
        from redbeat import RedBeatSchedulerEntry
        import redis as redis_lib

        broker_url = celery_app.conf.broker_url
        r = redis_lib.from_url(broker_url, decode_responses=True, socket_connect_timeout=3)

        prefix = celery_app.conf.get('redbeat_key_prefix', 'redbeat:')

        # Obtener todas las claves de tareas.
        # Excluir claves internas de redbeat:
        #   redbeat::lock     → mutex distribuido (tipo string)
        #   redbeat::statics  → metadatos internos (tipo string/set)
        #   redbeat::schedule → índice del scheduler (tipo zset)
        #   redbeat:<name>:meta → metadatos de cada entrada
        # Las entradas válidas son redbeat:<name> donde <name> no empieza con ':'
        all_keys = r.keys(f'{prefix}*')
        entry_keys = [
            k for k in all_keys
            if not k.endswith(':meta')
            and not k[len(prefix):].startswith(':')   # filtra ::lock, ::statics, etc.
        ]

        schedules = []
        for key in entry_keys:
            try:
                entry = RedBeatSchedulerEntry.from_key(key, app=celery_app)
                schedule_info = _serialize_schedule(entry)
                schedules.append(schedule_info)
            except Exception as e:
                logger.warning(f"[celery_api] No se pudo leer entry {key}: {e}")

        # Ordenar por nombre
        schedules.sort(key=lambda s: s['name'])
        return _ok(schedules)

    except Exception as exc:
        logger.error(f"[celery_api] list_schedules error: {exc}", exc_info=True)
        return _err(f"Error al leer schedules: {exc}", 500)


def _serialize_schedule(entry):
    """Convierte un RedBeatSchedulerEntry a dict serializable."""
    from celery.schedules import crontab

    schedule = entry.schedule
    schedule_type = 'unknown'
    cron_fields = {}

    if isinstance(schedule, crontab):
        schedule_type = 'crontab'
        cron_fields = {
            'minute':       str(schedule._orig_minute),
            'hour':         str(schedule._orig_hour),
            'day_of_week':  str(schedule._orig_day_of_week),
            'day_of_month': str(schedule._orig_day_of_month),
            'month_of_year':str(schedule._orig_month_of_year),
        }
    elif hasattr(schedule, 'seconds'):
        schedule_type = 'interval'
        cron_fields = {'seconds': str(int(schedule.seconds))}

    last_run = None
    if entry.last_run_at:
        last_run = entry.last_run_at.isoformat()

    return {
        'key':              entry.key,
        'name':             entry.name,
        'task':             entry.task,
        'schedule_type':    schedule_type,
        'cron_fields':      cron_fields,
        'enabled':          getattr(entry, 'enabled', True),
        'last_run_at':      last_run,
        'total_run_count':  getattr(entry, 'total_run_count', 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. ACTUALIZAR SCHEDULE (cron / habilitado)
# ─────────────────────────────────────────────────────────────────────────────

@api_celery_admin.route('/schedules/<path:entry_name>', methods=['PUT'])
@login_required
@permission_required('admin_celery.api.manage')
def update_schedule(entry_name):
    """
    Actualiza el schedule de una tarea en redbeat.

    Body JSON:
      enabled      (bool, opcional)
      cron_fields  (dict, opcional) — { minute, hour, day_of_week, day_of_month, month_of_year }
    """
    try:
        from redbeat import RedBeatSchedulerEntry
        from celery.schedules import crontab

        body = request.get_json(silent=True) or {}

        prefix = celery_app.conf.get('redbeat_key_prefix', 'redbeat:')
        key    = f'{prefix}{entry_name}'

        entry = RedBeatSchedulerEntry.from_key(key, app=celery_app)

        # Actualizar habilitado/deshabilitado
        if 'enabled' in body:
            entry.enabled = bool(body['enabled'])

        # Actualizar expresión cron
        if 'cron_fields' in body:
            cf = body['cron_fields']
            # Obtener valores actuales como base
            current = entry.schedule
            if isinstance(current, crontab):
                new_schedule = crontab(
                    minute       = cf.get('minute',        str(current._orig_minute)),
                    hour         = cf.get('hour',          str(current._orig_hour)),
                    day_of_week  = cf.get('day_of_week',   str(current._orig_day_of_week)),
                    day_of_month = cf.get('day_of_month',  str(current._orig_day_of_month)),
                    month_of_year= cf.get('month_of_year', str(current._orig_month_of_year)),
                )
                entry.schedule = new_schedule
            else:
                return _err("Solo se puede editar el cron de entradas de tipo 'crontab'.")

        entry.save()

        logger.info(
            f"[celery_api] Schedule actualizado: {entry_name} por user {current_user.id}"
        )

        return _ok(_serialize_schedule(entry))

    except Exception as exc:
        logger.error(f"[celery_api] update_schedule error: {exc}", exc_info=True)
        return _err(f"Error al actualizar schedule: {exc}", 500)

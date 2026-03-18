"""
Señales de Celery para registrar cada ejecución de tarea en TaskLog
y emitir eventos Socket.IO en tiempo real al panel de administración.

Se conectan al final de make_celery() en app/celery_app.py.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def register_task_signals(app, socketio_instance):
    """
    Conecta las señales de Celery. Recibe el app Flask y la instancia de
    SocketIO ya configurada con message_queue (Redis), para poder emitir
    eventos al cliente web desde el proceso del worker.
    """
    from celery.signals import task_prerun, task_success, task_failure, task_retry

    # ─── Helper: emit Socket.IO sin lanzar error si falla ─────────────────────

    def _emit(event, data):
        try:
            socketio_instance.emit(event, data, namespace='/worker')
        except Exception as exc:
            logger.debug(f"[signals] Socket.IO emit falló ({event}): {exc}")

    # ─── task_prerun → tarea iniciada ─────────────────────────────────────────

    @task_prerun.connect
    def on_task_prerun(task_id, task, args, kwargs, **extra):
        with app.app_context():
            try:
                from app import db
                from app.models.task_log import TaskLog

                # Evitar duplicados si ya existe (p.ej. reintento)
                existing = TaskLog.query.filter_by(task_id=task_id).first()
                if existing:
                    existing.status     = 'started'
                    existing.started_at = datetime.utcnow()
                else:
                    log = TaskLog(
                        task_id      = task_id,
                        task_name    = task.name,
                        status       = 'started',
                        started_at   = datetime.utcnow(),
                        kwargs       = kwargs or {},
                        triggered_by = getattr(task.request, '_triggered_by', 'scheduled'),
                        triggered_by_user_id = getattr(task.request, '_triggered_by_user_id', None),
                    )
                    db.session.add(log)

                db.session.commit()

                _emit('task_started', {
                    'task_id':   task_id,
                    'task_name': task.name,
                    'status':    'started',
                    'started_at': datetime.utcnow().isoformat(),
                })
            except Exception as exc:
                logger.error(f"[signals] on_task_prerun error: {exc}", exc_info=True)

    # ─── task_success → tarea completada exitosamente ─────────────────────────

    @task_success.connect
    def on_task_success(sender, result, **extra):
        task_id = sender.request.id
        with app.app_context():
            try:
                from app import db
                from app.models.task_log import TaskLog

                log = TaskLog.query.filter_by(task_id=task_id).first()
                if log:
                    log.status      = 'success'
                    log.finished_at = datetime.utcnow()
                    log.result      = result if isinstance(result, dict) else {'value': str(result)}
                    db.session.commit()

                _emit('task_success', {
                    'task_id':     task_id,
                    'task_name':   sender.name,
                    'status':      'success',
                    'finished_at': datetime.utcnow().isoformat(),
                    'result':      result,
                })
            except Exception as exc:
                logger.error(f"[signals] on_task_success error: {exc}", exc_info=True)

    # ─── task_failure → tarea fallida ─────────────────────────────────────────

    @task_failure.connect
    def on_task_failure(task_id, exception, traceback, sender, einfo, **extra):
        with app.app_context():
            try:
                from app import db
                from app.models.task_log import TaskLog

                log = TaskLog.query.filter_by(task_id=task_id).first()
                if log:
                    log.status        = 'failure'
                    log.finished_at   = datetime.utcnow()
                    log.error_message = f"{type(exception).__name__}: {exception}"
                    db.session.commit()

                _emit('task_failure', {
                    'task_id':       task_id,
                    'task_name':     sender.name,
                    'status':        'failure',
                    'finished_at':   datetime.utcnow().isoformat(),
                    'error_message': f"{type(exception).__name__}: {exception}",
                })
            except Exception as exc:
                logger.error(f"[signals] on_task_failure error: {exc}", exc_info=True)

    # ─── task_retry → tarea reintentando ──────────────────────────────────────

    @task_retry.connect
    def on_task_retry(request, reason, einfo, **extra):
        task_id = request.id
        with app.app_context():
            try:
                from app import db
                from app.models.task_log import TaskLog

                log = TaskLog.query.filter_by(task_id=task_id).first()
                if log:
                    log.status        = 'retry'
                    log.error_message = str(reason)
                    db.session.commit()

                _emit('task_retry', {
                    'task_id': task_id,
                    'status':  'retry',
                    'reason':  str(reason),
                })
            except Exception as exc:
                logger.error(f"[signals] on_task_retry error: {exc}", exc_info=True)

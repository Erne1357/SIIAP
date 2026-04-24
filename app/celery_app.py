from app.extensions import celery
from celery.schedules import crontab


def init_celery(app):
    """
    Configura la instancia de Celery ya creada en extensions.py con el contexto de la app Flask.
    """
    celery.conf.update(
        broker_url=app.config['CELERY_BROKER_URL'],
        result_backend=app.config['CELERY_RESULT_BACKEND'],
        timezone=app.config.get('CELERY_TIMEZONE', 'America/Ciudad_Juarez'),
        task_serializer=app.config.get('CELERY_TASK_SERIALIZER', 'json'),
        result_serializer=app.config.get('CELERY_RESULT_SERIALIZER', 'json'),
        accept_content=app.config.get('CELERY_ACCEPT_CONTENT', ['json']),
        task_track_started=app.config.get('CELERY_TASK_TRACK_STARTED', True),
        task_time_limit=app.config.get('CELERY_TASK_TIME_LIMIT', 300),
        task_soft_time_limit=app.config.get('CELERY_TASK_SOFT_TIME_LIMIT', 240),
        broker_connection_retry_on_startup=True,

        # ── Redbeat: scheduler con respaldo en Redis ──────────────────────────
        # Permite editar el schedule en tiempo real desde la UI sin reiniciar.
        beat_scheduler='redbeat.RedBeatScheduler',
        redbeat_redis_url=app.config['CELERY_BROKER_URL'],
        redbeat_lock_timeout=600,  # Aumentamos timeout a 10 min para evitar LockNotOwnedError
        beat_max_loop_interval=30, # Forzamos tick cada 30s para renovar el lock a tiempo

        # Tareas periódicas — se migran automáticamente a Redis en el primer
        # arranque de celery-beat con RedBeatScheduler.
        beat_schedule={
            # Limpia archivos de procesos de admisión expirados — todos los días a las 02:00
            'cleanup-expired-admission-files': {
                'task': 'app.tasks.maintenance.cleanup_expired_admission_files',
                'schedule': crontab(hour=2, minute=0),
            },
            # Aplica políticas de retención definidas en RetentionPolicy — todos los lunes a las 03:00
            'apply-retention-policies': {
                'task': 'app.tasks.maintenance.apply_retention_policies',
                'schedule': crontab(hour=3, minute=0, day_of_week=1),
            },
            # Limpia notificaciones leídas con más de 30 días — todos los días a las 04:00
            'cleanup-old-notifications': {
                'task': 'app.tasks.maintenance.cleanup_old_notifications',
                'schedule': crontab(hour=4, minute=0),
            },
            # Revisa diferimientos: expira vencidos y notifica próximos a vencer — diario a las 08:00
            'check-deferral-expirations': {
                'task': 'app.tasks.maintenance.check_deferral_expirations',
                'schedule': crontab(hour=8, minute=0),
            },
            # Notifica estudiantes sin inscripción semestral confirmada — lunes a las 09:00
            'notify-pending-permanence-docs': {
                'task': 'app.tasks.maintenance.notify_pending_permanence_docs',
                'schedule': crontab(hour=9, minute=0, day_of_week=1),
            },
            # Recordatorio 24h antes de cada evento — diario a las 09:00
            'event-reminders-24h': {
                'task': 'app.tasks.events.dispatch_reminders_24h',
                'schedule': crontab(hour=9, minute=0),
            },
            # Recordatorio 2h antes de cada evento — cada 15 minutos
            'event-reminders-2h': {
                'task': 'app.tasks.events.dispatch_reminders_2h',
                'schedule': crontab(minute='*/15'),
            },
        },
    )

    celery.main = app.import_name

    # Registrar módulos de tareas explícitamente para que el worker los descubra
    celery.conf.include = [
        'app.tasks.maintenance',
        'app.tasks.notifications',
        'app.tasks.events',
    ]

    # Hace que cada tarea se ejecute dentro del contexto de la app Flask
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # Registra las señales para logging de tareas + eventos Socket.IO en tiempo real
    from app.extensions import socketio
    from app.tasks.signals import register_task_signals
    # Nota: socketio ya debe estar init_app-eado o al menos instanciado.
    register_task_signals(app, socketio)

    return celery

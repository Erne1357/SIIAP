from celery import Celery
from celery.schedules import crontab


def make_celery(app=None):
    """
    Crea y configura la instancia de Celery integrada con Flask.

    Cuando se llama sin argumentos (desde el worker/beat), crea el app de Flask
    internamente. Cuando se llama con un app existente (desde create_app),
    usa ese contexto directamente.
    """
    if app is None:
        from app import create_app
        app = create_app()

    celery = Celery(app.import_name)

    # Registrar módulos de tareas explícitamente para que el worker los descubra
    celery.conf.include = [
        'app.tasks.maintenance',
        'app.tasks.notifications',
    ]

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

        # Tareas periódicas (Celery Beat)
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
        },
    )

    # Hace que cada tarea se ejecute dentro del contexto de la app Flask
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


# Instancia de Celery que usan los workers al invocar:
#   celery -A app.celery_app.celery worker --loglevel=info
#   celery -A app.celery_app.celery beat  --loglevel=info
celery = make_celery()

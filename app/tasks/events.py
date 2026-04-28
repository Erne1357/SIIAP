"""
Tareas Celery para eventos — dispatcher de recordatorios automáticos.

Las entradas de beat_schedule viven en app/celery_app.py:
- event-reminders-24h: diario 09:00 AM
- event-reminders-2h:  cada 15 minutos
"""

import logging
from app.extensions import celery

logger = logging.getLogger(__name__)


@celery.task(
    name='app.tasks.events.dispatch_reminders_24h',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def dispatch_reminders_24h(self):
    """Envía recordatorios 24 horas antes del evento."""
    from app.services.event_reminder_service import EventReminderService
    try:
        stats = EventReminderService.dispatch_due_reminders('24h')
        logger.info(f"[dispatch_reminders_24h] {stats}")
        return stats
    except Exception as exc:
        logger.exception(f"[dispatch_reminders_24h] error: {exc}")
        raise self.retry(exc=exc)


@celery.task(
    name='app.tasks.events.dispatch_reminders_2h',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def dispatch_reminders_2h(self):
    """Envía recordatorios 2 horas antes del evento."""
    from app.services.event_reminder_service import EventReminderService
    try:
        stats = EventReminderService.dispatch_due_reminders('2h')
        logger.info(f"[dispatch_reminders_2h] {stats}")
        return stats
    except Exception as exc:
        logger.exception(f"[dispatch_reminders_2h] error: {exc}")
        raise self.retry(exc=exc)

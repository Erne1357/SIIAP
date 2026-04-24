"""
Tareas Celery para eventos — dispatcher de recordatorios automáticos.

Las entradas de beat_schedule viven en app/celery_app.py:
- event-reminders-24h: diario 09:00 AM
- event-reminders-2h:  cada 15 minutos
"""

import logging
from app.extensions import celery

logger = logging.getLogger(__name__)


@celery.task(name='app.tasks.events.dispatch_reminders_24h')
def dispatch_reminders_24h():
    """Envía recordatorios 24 horas antes del evento."""
    from app.services.event_reminder_service import EventReminderService
    try:
        stats = EventReminderService.dispatch_due_reminders('24h')
        logger.info(f"[dispatch_reminders_24h] {stats}")
        return stats
    except Exception as e:
        logger.exception(f"[dispatch_reminders_24h] error: {e}")
        raise


@celery.task(name='app.tasks.events.dispatch_reminders_2h')
def dispatch_reminders_2h():
    """Envía recordatorios 2 horas antes del evento."""
    from app.services.event_reminder_service import EventReminderService
    try:
        stats = EventReminderService.dispatch_due_reminders('2h')
        logger.info(f"[dispatch_reminders_2h] {stats}")
        return stats
    except Exception as e:
        logger.exception(f"[dispatch_reminders_2h] error: {e}")
        raise

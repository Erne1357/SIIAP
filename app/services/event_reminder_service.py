"""
EventReminderService — despacha recordatorios automáticos de eventos
(24h y 2h antes del inicio). Idempotente vía EventReminderLog.
"""

from datetime import timedelta
import logging

from app import db
from app.utils.datetime_utils import now_local
from app.models.event import Event, EventAttendance, EventInvitation, EventReminderLog
from app.models.appointment import Appointment
from app.models.event import EventSlot, EventWindow

logger = logging.getLogger(__name__)

# Ventanas de tolerancia para el lookup (Celery beat no es segundo-preciso).
WINDOWS = {
    '24h': (timedelta(hours=23), timedelta(hours=25)),
    '2h':  (timedelta(hours=1, minutes=45), timedelta(hours=2, minutes=15)),
}


class EventReminderService:
    """Dispatcher de recordatorios periódicos."""

    @staticmethod
    def dispatch_due_reminders(window_type: str) -> dict:
        """
        Busca eventos cuyo inicio cae en la ventana indicada y envía recordatorios.
        Idempotencia garantizada por EventReminderLog (query antes de crear).

        Returns: {'sent': N, 'skipped': M, 'failed': K}
        """
        if window_type not in WINDOWS:
            raise ValueError(f"window_type debe ser uno de {list(WINDOWS.keys())}")

        lower, upper = WINDOWS[window_type]
        ref_start = now_local() + lower
        ref_end = now_local() + upper

        stats = {'sent': 0, 'skipped': 0, 'failed': 0}

        # --- Eventos multiple/unlimited (usar event_date) ---
        multi_events = Event.query.filter(
            Event.status == 'published',
            Event.reminders_enabled == True,
            Event.capacity_type != 'single',
            Event.event_date.isnot(None),
            Event.event_date >= ref_start,
            Event.event_date <= ref_end
        ).all()

        for ev in multi_events:
            EventReminderService._send_for_multi_event(ev, window_type, stats)

        # --- Eventos single (1:1) — usar slots con Appointments activos ---
        single_appts = db.session.query(Appointment, EventSlot, Event).join(
            EventSlot, Appointment.slot_id == EventSlot.id
        ).join(
            EventWindow, EventSlot.event_window_id == EventWindow.id
        ).join(
            Event, EventWindow.event_id == Event.id
        ).filter(
            Appointment.status == 'scheduled',
            Event.status == 'published',
            Event.reminders_enabled == True,
            Event.capacity_type == 'single',
            EventSlot.starts_at >= ref_start,
            EventSlot.starts_at <= ref_end
        ).all()

        for appt, slot, ev in single_appts:
            EventReminderService._send_for_single_appointment(
                ev, appt, slot, window_type, stats
            )

        return stats

    @staticmethod
    def _send_for_multi_event(event: Event, window_type: str, stats: dict):
        """Envía recordatorios a registered + invitados accepted de un evento multiple."""
        user_ids = set()

        for att in EventAttendance.query.filter_by(
            event_id=event.id, status='registered'
        ).all():
            user_ids.add(att.user_id)

        for inv in EventInvitation.query.filter_by(
            event_id=event.id, status='accepted'
        ).all():
            user_ids.add(inv.user_id)

        slot_datetime = event.event_date.strftime('%d/%m/%Y %H:%M') if event.event_date else 'Por definir'

        for user_id in user_ids:
            EventReminderService._dispatch_one(
                event=event,
                user_id=user_id,
                window_type=window_type,
                appointment_id=None,
                slot_datetime=slot_datetime,
                stats=stats
            )

    @staticmethod
    def _send_for_single_appointment(event: Event, appointment: Appointment, slot: EventSlot, window_type: str, stats: dict):
        """Envía recordatorio al applicant de una cita 1:1."""
        slot_datetime = slot.starts_at.strftime('%d/%m/%Y %H:%M')
        EventReminderService._dispatch_one(
            event=event,
            user_id=appointment.applicant_id,
            window_type=window_type,
            appointment_id=appointment.id,
            slot_datetime=slot_datetime,
            stats=stats
        )

    @staticmethod
    def _dispatch_one(event: Event, user_id: int, window_type: str,
                      appointment_id: int | None, slot_datetime: str, stats: dict):
        """
        Crea log + notificación + email. Idempotente: salta si ya existe log.
        """
        from app.services.notification_service import NotificationService

        existing = EventReminderLog.query.filter_by(
            event_id=event.id,
            user_id=user_id,
            reminder_type=window_type,
            appointment_id=appointment_id
        ).first()
        if existing:
            stats['skipped'] += 1
            return

        try:
            log = EventReminderLog(
                event_id=event.id,
                user_id=user_id,
                reminder_type=window_type,
                appointment_id=appointment_id
            )
            db.session.add(log)
            db.session.flush()

            NotificationService.notify_event_reminder(
                user_id=user_id,
                event=event,
                reminder_type=window_type,
                slot_datetime=slot_datetime
            )
            db.session.commit()
            stats['sent'] += 1
        except Exception as e:
            db.session.rollback()
            logger.exception(
                f"[event_reminder] fallo user_id={user_id} event_id={event.id} type={window_type}: {e}"
            )
            stats['failed'] += 1

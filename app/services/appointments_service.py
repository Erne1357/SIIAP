from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app import db
from app.models.event import EventSlot, EventWindow
from app.models.appointment import Appointment, AppointmentChangeRequest
from app.models.event import Event

class AppointmentsService:
    @staticmethod
    def assign_slot(event_id:int, slot_id:int, applicant_id:int, assigned_by:int, notes:str|None=None) -> Appointment:
        # Lock del slot para evitar carrera
        slot = db.session.execute(
            select(EventSlot).where(EventSlot.id == slot_id).with_for_update()
        ).scalar_one_or_none()
        if not slot:
            raise ValueError("Slot no encontrado")

        # validar que el slot pertenece al event
        win = db.session.get(EventWindow, slot.event_window_id)
        ev = db.session.get(Event, win.event_id) if win else None
        if not ev or ev.id != event_id:
            raise ValueError("El slot no pertenece al evento")

        if slot.status != 'free':
            raise ValueError("El slot no está disponible")

        slot.status = 'booked'
        slot.held_by = applicant_id
        appt = Appointment(
            event_id=event_id,
            slot_id=slot_id,
            applicant_id=applicant_id,
            assigned_by=assigned_by,
            status='scheduled',
            notes=notes,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(appt)
        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            raise ValueError("El alumno ya tiene una cita para este evento o el slot ya fue tomado") from e
        return appt

    @staticmethod
    def cancel_appointment(appointment_id:int, reason:str|None=None):
        appt = db.session.get(Appointment, appointment_id)
        if not appt:
            raise ValueError("Appointment no encontrado")
        slot = db.session.get(EventSlot, appt.slot_id)
        if slot and slot.status == 'booked':
            slot.status = 'free'
            slot.held_by = None
            slot.hold_expires_at = None
        appt.status = 'cancelled'
        if reason:
            appt.notes = (appt.notes + "\n" if appt.notes else "") + f"[CANCEL]: {reason}"
        db.session.commit()
        return appt

    @staticmethod
    def request_change(appointment_id:int, requested_by:int, reason:str|None=None, suggestions:str|None=None) -> AppointmentChangeRequest:
        appt = db.session.get(Appointment, appointment_id)
        if not appt:
            raise ValueError("Appointment no encontrado")

        acr = AppointmentChangeRequest(
            appointment_id=appointment_id,
            requested_by=requested_by,
            reason=reason,
            suggestions=suggestions,
            status='pending',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(acr)
        db.session.commit()
        return acr

    @staticmethod
    def decide_change(request_id:int, status:str, decided_by:int, new_slot_id:int|None=None):
        if status not in ('accepted','rejected','cancelled'):
            raise ValueError("status inválido")

        acr = db.session.get(AppointmentChangeRequest, request_id)
        if not acr:
            raise ValueError("Solicitud de cambio no encontrada")

        appt = db.session.get(Appointment, acr.appointment_id)
        if not appt:
            raise ValueError("Appointment no encontrado")

        acr.status = status
        acr.decided_by = decided_by
        acr.decided_at = datetime.now(timezone.utc)

        if status == 'accepted':
            if not new_slot_id:
                raise ValueError("Se requiere new_slot_id para aceptar")
            # liberar slot previo y asignar nuevo con lock
            old_slot = db.session.get(EventSlot, appt.slot_id)
            new_slot = db.session.execute(
                select(EventSlot).where(EventSlot.id == new_slot_id).with_for_update()
            ).scalar_one_or_none()
            if not new_slot or new_slot.status != 'free':
                raise ValueError("El nuevo slot no está disponible")

            # reasignar
            if old_slot and old_slot.status == 'booked':
                old_slot.status = 'free'
            new_slot.status = 'booked'
            appt.slot_id = new_slot_id
            appt.status = 'scheduled'

        db.session.commit()
        return acr

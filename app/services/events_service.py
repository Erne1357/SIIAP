from datetime import datetime, date, time, timedelta
from app import db
from app.models.event import Event, EventWindow, EventSlot

class EventsService:
    @staticmethod
    def create_event(program_id:int|None, type_:str, title:str, description:str|None, location:str|None, created_by:int, visible_to_students:bool=True) -> Event:
        ev = Event(
            program_id=program_id,
            type=type_ or 'interview',
            title=title,
            description=description,
            location=location,
            created_by=created_by,
            visible_to_students=visible_to_students
        )
        db.session.add(ev)
        db.session.commit()
        return ev

    @staticmethod
    def add_window(event_id:int, window_date:date, start:time, end:time, slot_minutes:int, timezone_str:str='America/Ciudad_Juarez') -> EventWindow:
        if start >= end:
            raise ValueError("start_time debe ser menor a end_time")
        if slot_minutes not in (15,20,30,45,60):
            raise ValueError("slot_minutes inválido")

        win = EventWindow(
            event_id=event_id,
            date=window_date,
            start_time=start,
            end_time=end,
            slot_minutes=slot_minutes,
            timezone=timezone_str
        )
        db.session.add(win)
        db.session.commit()
        return win

    @staticmethod
    def generate_slots(window_id:int) -> list[EventSlot]:
        win = db.session.get(EventWindow, window_id)
        if not win:
            raise ValueError("EventWindow no encontrado")

        # construir timestamps combinando date + times (naive, asume zona manejada en capa superior)
        starts = datetime.combine(win.date, win.start_time)
        ends   = datetime.combine(win.date, win.end_time)

        created = []
        cursor = starts
        while cursor < ends:
            slot_end = cursor + timedelta(minutes=win.slot_minutes)
            if slot_end > ends:
                break

            slot = EventSlot(
                event_window_id=win.id,
                starts_at=cursor,
                ends_at=slot_end,
                status='free'
            )
            db.session.add(slot)
            try:
                db.session.flush()  # para respetar UNIQUE(event_window_id, starts_at)
                created.append(slot)
            except Exception:
                db.session.rollback()
                # ya existía (idempotente) → salta
                db.session.begin()

            cursor = slot_end

        db.session.commit()
        return created

    @staticmethod
    def list_slots(event_id:int=None, status:str=None):
        q = db.session.query(EventSlot).join(EventWindow, EventWindow.id == EventSlot.event_window_id)
        if event_id:
            q = q.join(Event, Event.id == EventWindow.event_id).filter(Event.id == event_id)
        if status:
            q = q.filter(EventSlot.status == status)
        return q.order_by(EventSlot.starts_at.asc()).all()

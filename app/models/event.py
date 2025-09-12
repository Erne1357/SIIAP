from app import db
from datetime import datetime, timezone

class Event(db.Model):
    __tablename__ = 'event'

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id', ondelete='CASCADE', onupdate='CASCADE'))
    type = db.Column(db.String(50), nullable=False, default='interview')  # interview | workshop | etc.
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    visible_to_students = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    windows = db.relationship('EventWindow', back_populates='event', cascade='all, delete-orphan')


class EventWindow(db.Model):
    __tablename__ = 'event_window'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_minutes = db.Column(db.Integer, nullable=False)  # 15|20|30|45|60
    timezone = db.Column(db.String(50), default='America/Ciudad_Juarez')

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    event = db.relationship('Event', back_populates='windows')
    slots = db.relationship('EventSlot', back_populates='window', cascade='all, delete-orphan')


class EventSlot(db.Model):
    __tablename__ = 'event_slot'

    id = db.Column(db.Integer, primary_key=True)
    event_window_id = db.Column(db.Integer, db.ForeignKey('event_window.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='free')  # free|held|booked|cancelled
    held_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL', onupdate='CASCADE'))
    hold_expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    window = db.relationship('EventWindow', back_populates='slots')

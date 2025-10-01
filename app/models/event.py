from app import db
from datetime import datetime, timezone

class Event(db.Model):
    __tablename__ = 'event'

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id', ondelete='CASCADE', onupdate='CASCADE'))
    type = db.Column(db.String(50), nullable=False, default='interview')
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    visible_to_students = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    capacity_type = db.Column(db.String(20), nullable=False, default='single')  # single|multiple|unlimited
    max_capacity = db.Column(db.Integer, nullable=True)  # null para unlimited
    requires_registration = db.Column(db.Boolean, nullable=False, default=True)
    allows_attendance_tracking = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default='published')  # draft|published|ongoing|completed|cancelled

    event_date = db.Column(db.DateTime, nullable=True)  # Fecha/hora general del evento
    event_end_date = db.Column(db.DateTime, nullable=True)  # Para eventos de varios días

    windows = db.relationship('EventWindow', back_populates='event', cascade='all, delete-orphan')


class EventWindow(db.Model):
    __tablename__ = 'event_window'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_minutes = db.Column(db.Integer, nullable=False)
    timezone = db.Column(db.String(50), default='America/Ciudad_Juarez')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # ========== NUEVOS CAMPOS ==========
    slots_generated = db.Column(db.Boolean, nullable=False, default=False)
    current_capacity = db.Column(db.Integer, nullable=False, default=0)

    event = db.relationship('Event', back_populates='windows')
    slots = db.relationship('EventSlot', back_populates='window', cascade='all, delete-orphan')


class EventSlot(db.Model):
    __tablename__ = 'event_slot'

    id = db.Column(db.Integer, primary_key=True)
    event_window_id = db.Column(db.Integer, db.ForeignKey('event_window.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='free')
    held_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL', onupdate='CASCADE'))
    hold_expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    window = db.relationship('EventWindow', back_populates='slots')


class EventAttendance(db.Model):
    """Nueva tabla para eventos con capacidad múltiple/ilimitada"""
    __tablename__ = 'event_attendance'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='registered')  # registered|attended|no_show
    registered_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    attended_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Relaciones
    event = db.relationship('Event')
    user = db.relationship('User')

class EventInvitation(db.Model):
    """Invitaciones a eventos para estudiantes específicos"""
    __tablename__ = 'event_invitation'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'))
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending|accepted|rejected
    invited_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    responded_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    # Relaciones
    event = db.relationship('Event', foreign_keys=[event_id])
    user = db.relationship('User', foreign_keys=[user_id])
    inviter = db.relationship('User', foreign_keys=[invited_by])
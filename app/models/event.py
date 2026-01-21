from app import db
from datetime import datetime, timezone
from app.utils.datetime_utils import now_local

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
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local, nullable=False)
    
    capacity_type = db.Column(db.String(20), nullable=False, default='single')  # single|multiple|unlimited
    max_capacity = db.Column(db.Integer, nullable=True)  # null para unlimited
    requires_registration = db.Column(db.Boolean, nullable=False, default=True)
    allows_attendance_tracking = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default='published')  # draft|published|ongoing|completed|cancelled

    event_date = db.Column(db.DateTime, nullable=True)  # Fecha/hora general del evento
    event_end_date = db.Column(db.DateTime, nullable=True)  # Para eventos de varios días

    windows = db.relationship('EventWindow', back_populates='event', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'program_id': self.program_id,
            'type': self.type,
            'title': self.title,
            'description': self.description,
            'location': self.location,
            'created_by': self.created_by,
            'visible_to_students': self.visible_to_students,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'capacity_type': self.capacity_type,
            'max_capacity': self.max_capacity,
            'requires_registration': self.requires_registration,
            'allows_attendance_tracking': self.allows_attendance_tracking,
            'status': self.status,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'event_end_date': self.event_end_date.isoformat() if self.event_end_date else None
        }


class EventWindow(db.Model):
    __tablename__ = 'event_window'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_minutes = db.Column(db.Integer, nullable=False)
    timezone = db.Column(db.String(50), default='America/Ciudad_Juarez')
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local, nullable=False)
    
    # ========== NUEVOS CAMPOS ==========
    slots_generated = db.Column(db.Boolean, nullable=False, default=False)
    current_capacity = db.Column(db.Integer, nullable=False, default=0)

    event = db.relationship('Event', back_populates='windows')
    slots = db.relationship('EventSlot', back_populates='window', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'date': self.date.isoformat() if self.date else None,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'slot_minutes': self.slot_minutes,
            'timezone': self.timezone,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'slots_generated': self.slots_generated,
            'current_capacity': self.current_capacity
        }


class EventSlot(db.Model):
    __tablename__ = 'event_slot'

    id = db.Column(db.Integer, primary_key=True)
    event_window_id = db.Column(db.Integer, db.ForeignKey('event_window.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='free')
    held_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL', onupdate='CASCADE'))
    hold_expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local, nullable=False)

    window = db.relationship('EventWindow', back_populates='slots')
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_window_id': self.event_window_id,
            'starts_at': self.starts_at.isoformat() if self.starts_at else None,
            'ends_at': self.ends_at.isoformat() if self.ends_at else None,
            'status': self.status,
            'held_by': self.held_by,
            'hold_expires_at': self.hold_expires_at.isoformat() if self.hold_expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class EventAttendance(db.Model):
    """Nueva tabla para eventos con capacidad múltiple/ilimitada"""
    __tablename__ = 'event_attendance'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='registered')  # registered|attended|no_show
    registered_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now())
    attended_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Relaciones
    event = db.relationship('Event')
    user = db.relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'user_id': self.user_id,
            'status': self.status,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'attended_at': self.attended_at.isoformat() if self.attended_at else None,
            'notes': self.notes
        }

class EventInvitation(db.Model):
    """Invitaciones a eventos para estudiantes específicos"""
    __tablename__ = 'event_invitation'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'))
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending|accepted|rejected
    invited_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now())
    responded_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    # Relaciones
    event = db.relationship('Event', foreign_keys=[event_id])
    user = db.relationship('User', foreign_keys=[user_id])
    inviter = db.relationship('User', foreign_keys=[invited_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'user_id': self.user_id,
            'invited_by': self.invited_by,
            'status': self.status,
            'invited_at': self.invited_at.isoformat() if self.invited_at else None,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'notes': self.notes
        }
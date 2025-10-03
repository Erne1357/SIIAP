from app import db
from datetime import datetime, timezone

class Appointment(db.Model):
    __tablename__ = 'appointment'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('event_slot.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False, unique=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL', onupdate='CASCADE'))
    status = db.Column(db.String(20), nullable=False, default='scheduled')  # scheduled|done|no_show|cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Nota: si quieres acceder a slot/event como objetos, puedes definir relaciones viewonly aquí.


class AppointmentChangeRequest(db.Model):
    __tablename__ = 'appointment_change_request'

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    reason = db.Column(db.Text)
    suggestions = db.Column(db.Text)  # JSON textual o texto libre con propuestas
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending|accepted|rejected|cancelled
    decided_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL', onupdate='CASCADE'))
    decided_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

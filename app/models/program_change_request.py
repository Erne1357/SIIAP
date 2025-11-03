from app import db
from datetime import datetime, timezone
from app.utils.datetime_utils import now_local

class ProgramChangeRequest(db.Model):
    __tablename__ = 'program_change_request'

    id = db.Column(db.Integer, primary_key=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    from_program_id = db.Column(db.Integer, db.ForeignKey('program.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    to_program_id = db.Column(db.Integer, db.ForeignKey('program.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)

    reason = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending|approved|rejected|cancelled
    decided_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL', onupdate='CASCADE'))
    decided_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local, nullable=False)

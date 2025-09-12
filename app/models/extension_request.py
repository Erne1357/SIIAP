from app import db
from datetime import datetime, timezone

class ExtensionRequest(db.Model):
    __tablename__ = 'extension_request'

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)

    requested_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student' | 'coordinator'
    reason = db.Column(db.Text)

    requested_until = db.Column(db.DateTime)  # fecha sugerida por quien solicita (opcional)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending|granted|rejected

    granted_until = db.Column(db.DateTime)    # fecha otorgada
    condition_text = db.Column(db.Text)

    decided_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL', onupdate='CASCADE'))
    decided_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    submission = db.relationship('Submission', viewonly=True)

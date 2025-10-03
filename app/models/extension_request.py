# app/models/extension_request.py - Modelo actualizado
from app import db
from datetime import datetime, timezone

class ExtensionRequest(db.Model):
    __tablename__ = 'extension_request'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    archive_id = db.Column(db.Integer, db.ForeignKey('archive.id', ondelete='CASCADE'), nullable=False)
    program_step_id = db.Column(db.Integer, db.ForeignKey('program_step.id', ondelete='CASCADE'), nullable=False)
    
    # Información de la solicitud
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # student | coordinator
    reason = db.Column(db.Text, nullable=False)
    requested_until = db.Column(db.DateTime, nullable=False)
    
    # Estado y decisión
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | granted | rejected | cancelled
    decided_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'))
    decided_at = db.Column(db.DateTime)
    granted_until = db.Column(db.DateTime)
    condition_text = db.Column(db.Text)  # Condiciones específicas de la prórroga
    
    # Auditoría
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Relaciones
    user = db.relationship('User', foreign_keys=[user_id], backref='extension_requests')
    archive = db.relationship('Archive', backref='extension_requests')
    program_step = db.relationship('ProgramStep', backref='extension_requests')
    requester = db.relationship('User', foreign_keys=[requested_by])
    reviewer = db.relationship('User', foreign_keys=[decided_by])
    
    def __init__(self, user_id, archive_id, program_step_id, requested_by, reason, requested_until, role='student'):
        self.user_id = user_id
        self.archive_id = archive_id
        self.program_step_id = program_step_id
        self.requested_by = requested_by
        self.reason = reason
        self.requested_until = requested_until
        self.role = role
        self.status = 'pending'
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
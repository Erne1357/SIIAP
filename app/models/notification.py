from app import db
from datetime import datetime
from app.utils.datetime_utils import now_local


class Notification(db.Model):
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    priority = db.Column(db.String(20), default='medium', nullable=False)
    
    data = db.Column(db.JSON, nullable=True)
    
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    is_actionable = db.Column(db.Boolean, default=False, nullable=False)
    
    related_invitation_id = db.Column(db.Integer, db.ForeignKey('event_invitation.id', ondelete='SET NULL'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=now_local, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', backref='notifications')
    invitation = db.relationship('EventInvitation', backref='notification_ref', uselist=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'priority': self.priority,
            'data': self.data or {},
            'is_read': self.is_read,
            'is_deleted': self.is_deleted,
            'is_actionable': self.is_actionable,
            'related_invitation_id': self.related_invitation_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
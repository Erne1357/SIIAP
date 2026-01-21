from app import db
from datetime import datetime,timezone
from app.utils.datetime_utils import now_local

class Log(db.Model):
    __tablename__ = 'log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

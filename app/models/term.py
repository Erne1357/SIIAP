from app import db

class Term(db.Model):
    __tablename__ = 'term'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # '2025-1', '2025-2', etc.
    start_at = db.Column(db.Date, nullable=False)
    end_at = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='open')  # open|closed
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'start_at': self.start_at.isoformat() if self.start_at else None,
            'end_at': self.end_at.isoformat() if self.end_at else None,
            'status': self.status
        }

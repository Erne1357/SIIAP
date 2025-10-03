from app import db

class Term(db.Model):
    __tablename__ = 'term'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # '2025-1', '2025-2', etc.
    start_at = db.Column(db.Date, nullable=False)
    end_at = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='open')  # open|closed

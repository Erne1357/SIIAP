from app import db
from datetime import datetime

class Submission(db.Model):
    __tablename__ = 'submission'
    
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    review_date = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    step_id = db.Column(db.Integer, db.ForeignKey('step.id'), nullable=False)
    
    # Relación: Una submission puede tener varios archivos (archives)
    archives = db.relationship('Archive', backref='submission', lazy=True)
    
    def __init__(self, file_path, status, user_id, program_id, step_id, review_date=None):
        self.file_path = file_path
        self.status = status
        self.user_id = user_id
        self.program_id = program_id
        self.step_id = step_id
        self.review_date = review_date

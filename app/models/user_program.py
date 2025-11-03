from app import db
from datetime import datetime
from app.utils.datetime_utils import now_local

class UserProgram(db.Model):
    __tablename__ = 'user_program'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    enrollment_date = db.Column(db.DateTime, default=now_local)
    current_semester = db.Column(db.Integer)
    status = db.Column(db.String(50), nullable=False, default='active')
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local, nullable=False)

    user = db.relationship('User', back_populates='user_program')
    program = db.relationship('Program', back_populates='user_program')

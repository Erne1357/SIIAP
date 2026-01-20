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

    # Relacion con periodo de admision
    admission_period_id = db.Column(db.Integer, db.ForeignKey('academic_period.id'), nullable=True)

    user = db.relationship('User', back_populates='user_program')
    program = db.relationship('Program', back_populates='user_program')
    admission_period = db.relationship('AcademicPeriod', back_populates='user_programs')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'program_id': self.program_id,
            'enrollment_date': self.enrollment_date.isoformat() if self.enrollment_date else None,
            'current_semester': self.current_semester,
            'status': self.status,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'admission_period_id': self.admission_period_id
        }

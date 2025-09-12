from app import db
from datetime import datetime,timezone

class Submission(db.Model):
    __tablename__ = 'submission'
    
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    review_date = db.Column(db.DateTime)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewer_comment = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    archive_id = db.Column(db.Integer,db.ForeignKey('archive.id') , nullable = False)
    program_step_id = db.Column(db.Integer, db.ForeignKey('program_step.id') , nullable = False)
    period = db.Column(db.String(50), nullable=True)
    semester = db.Column(db.Integer, nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    uploaded_by_role = db.Column(db.String(20))  # 'student' | 'coordinator'
    deadline_at = db.Column(db.DateTime)         # fecha límite efectiva (si hay prórroga)
    is_in_extension = db.Column(db.Boolean, default=False, nullable=False)

    user          = db.relationship('User',foreign_keys=[user_id],back_populates='submissions')
    reviewer      = db.relationship('User',foreign_keys=[reviewer_id],back_populates='reviews')
    archive       = db.relationship('Archive',back_populates='submissions')
    program_step  = db.relationship('ProgramStep',back_populates='submissions')
    uploader = db.relationship('User', foreign_keys=[uploaded_by], viewonly=True)

    def __init__(self, file_path, status, user_id, archive_id, program_step_id, period, semester, review_date=None, reviewer_id=None, reviewer_comment=None):
        self.file_path = file_path
        self.status = status
        self.user_id = user_id
        self.archive_id = archive_id
        self.program_step_id = program_step_id
        self.review_date = review_date
        self.period = period
        self.semester = semester
        self.reviewer_id = reviewer_id
        self.reviewer_comment = reviewer_comment

from app import db
from app.utils.datetime_utils import now_local

class Archive(db.Model):
    __tablename__ = 'archive'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_downloadable = db.Column(db.Boolean, default=True)
    is_uploadable = db.Column(db.Boolean, default=True)
    file_path = db.Column(db.String(200))
    step_id = db.Column(db.Integer, db.ForeignKey('step.id'), nullable=False)
    allow_coordinator_upload = db.Column(db.Boolean,default=False,nullable=False)
    allow_extension_request = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=now_local, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local, nullable=False)

    step = db.relationship("Step", back_populates="archives")
    submissions = db.relationship('Submission', back_populates='archive')

    def __init__(self, name, description, file_path, step_id, is_downloadable=True, is_uploadable=True):
        self.name = name
        self.description = description
        self.file_path = file_path
        self.is_downloadable = is_downloadable
        self.step_id = step_id
        self.is_uploadable = is_uploadable

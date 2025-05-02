from app import db

class Archive(db.Model):
    __tablename__ = 'archive'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_downloadable = db.Column(db.Boolean, default=True)
    file_path = db.Column(db.String(200), nullable=False)
    step_id = db.Column(db.Integer, db.ForeignKey('step.id'), nullable=False)

    
    def __init__(self, name, description, file_path,step_id, is_downloadable=True):
        self.name = name
        self.description = description
        self.file_path = file_path
        self.is_downloadable = is_downloadable
        self.step_id = step_id

from app import db

class Program(db.Model):
    __tablename__ = 'program'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    coordinator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    
    def __init__(self, name, description, coordinator_id):
        self.name = name
        self.description = description
        self.coordinator_id = coordinator_id

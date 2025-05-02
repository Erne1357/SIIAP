from app import db

class Step(db.Model):
    __tablename__ = 'step'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    phase_id= db.Column(db.Integer, db.ForeignKey('phase.id'), nullable=False)
    
    
    def __init__(self, name, description, phase_id):
        self.name = name
        self.description = description
        self.phase_id = phase_id

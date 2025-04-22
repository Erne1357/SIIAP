from app import db

class Step(db.Model):
    __tablename__ = 'step'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    program_step_id = db.Column(db.Integer, db.ForeignKey('program_step.id'), nullable=False)
    
    
    def __init__(self, name, description, program_id):
        self.name = name
        self.description = description
        self.program_id = program_id

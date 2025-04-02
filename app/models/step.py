from app import db

class Step(db.Model):
    __tablename__ = 'step'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    
    # Relación: Un step puede tener muchas submissions
    submissions = db.relationship('Submission', backref='step', lazy=True)
    
    def __init__(self, name, description, program_id):
        self.name = name
        self.description = description
        self.program_id = program_id

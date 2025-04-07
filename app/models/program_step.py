from app import db

class ProgramStep(db.Model):
    __tablename__ = 'program_step'
    
    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    step_id = db.Column(db.Integer, db.ForeignKey('step.id'), nullable=False)
    
    step = db.relationship('Step', backref=db.backref('program_steps', cascade="all, delete-orphan"))
    program = db.relationship('Program', backref=db.backref('program_steps', cascade="all, delete-orphan"))

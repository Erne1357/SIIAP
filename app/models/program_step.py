from app import db

class ProgramStep(db.Model):
    __tablename__ = 'program_step'
    
    id = db.Column(db.Integer, primary_key=True)
    sequence = db.Column(db.Integer, nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    step_id = db.Column(db.Integer, db.ForeignKey('step.id'), nullable=False)
    
    program = db.relationship("Program", back_populates="program_steps")
    step    = db.relationship("Step",    back_populates="program_steps")
    submissions = db.relationship('Submission', back_populates='program_step')
    
    def to_dict(self):
        return {
            'id': self.id,
            'sequence': self.sequence,
            'program_id': self.program_id,
            'step_id': self.step_id
        }

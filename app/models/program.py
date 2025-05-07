from app import db
from sqlalchemy import asc
from app.models.step import Step
from app.models.program_step import ProgramStep

class Program(db.Model):
    __tablename__ = 'program'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    coordinator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    
    # 1) asociación con la tabla puente (incluye 'sequence')
    program_steps = db.relationship(
        "ProgramStep",
        back_populates="program",
        order_by="ProgramStep.sequence",
        cascade="all, delete-orphan",
    )

    # 2) vista directa a los pasos, sólo lectura
    steps = db.relationship(
        "Step",
        secondary="program_step",
        order_by="Step.phase_id",
        viewonly=True,
    )

    def __init__(self, name, description, coordinator_id):
        self.name = name
        self.description = description
        self.coordinator_id = coordinator_id

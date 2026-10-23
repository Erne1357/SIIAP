# app/models/curriculum_plan.py
from app import db
from app.utils.datetime_utils import now_local


class CurriculumPlan(db.Model):
    """
    A versioned study plan (retícula) of a program.

    Each student program is tied to the version it entered with
    (`UserProgram.curriculum_plan_id`), so changing the plan never rewrites
    the kardex of earlier generations. Exactly one version per program is
    current; `curriculum_service.set_current()` keeps it that way.
    """
    __tablename__ = 'curriculum_plan'
    __table_args__ = (
        db.UniqueConstraint('program_id', 'version', name='uq_curriculum_plan_program_version'),
        db.Index('uq_curriculum_plan_one_current', 'program_id', unique=True,
                 postgresql_where=db.text('is_current'), sqlite_where=db.text('is_current')),
    )

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    is_current = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)

    program = db.relationship('Program')
    subjects = db.relationship('Subject', back_populates='plan', order_by='Subject.sequence',
                               cascade='all, delete-orphan')

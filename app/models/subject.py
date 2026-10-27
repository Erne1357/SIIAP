# app/models/subject.py
from app import db

#: required — mandatory subject; elective_slot — a placeholder such as
#: "Optativa I" with a suggested semester; elective — a subject of the
#: program's elective bank, which fills a slot when a student takes it.
SUBJECT_KINDS = ('required', 'elective_slot', 'elective')


class Subject(db.Model):
    """A subject (materia) of a curriculum plan version."""
    __tablename__ = 'subject'
    __table_args__ = (
        db.UniqueConstraint('plan_id', 'key', name='uq_subject_plan_key'),
        db.CheckConstraint(
            "kind IN ('required', 'elective_slot', 'elective')", name='ck_subject_kind'),
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('curriculum_plan.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    # Seeded subjects arrive without key or credits; the UI flags them as incomplete.
    key = db.Column(db.String(20), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    credits = db.Column(db.Integer, nullable=True)
    suggested_semester = db.Column(db.Integer, nullable=True)
    kind = db.Column(db.String(20), nullable=False, default='required')
    sequence = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    plan = db.relationship('CurriculumPlan', back_populates='subjects')

    @property
    def is_incomplete(self) -> bool:
        return self.kind != 'elective_slot' and (not self.key or self.credits is None)

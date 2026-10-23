from app import db
from app.models.mixins import PublicUUIDMixin
from app.utils.datetime_utils import now_local

EXAM_STATUSES = ('scheduled', 'approved', 'suspended', 'cancelled')
EXAM_VERDICTS = ('unanimous', 'majority')


class GradeExam(PublicUUIDMixin, db.Model):
    """
    A grade examination of one student program (phase 6C). At most one is
    `scheduled` at a time; a suspended one is kept and a new one is scheduled.
    An approved exam titles the student (`academic_status='titled'`).
    """
    __tablename__ = 'grade_exam'
    __table_args__ = (
        db.CheckConstraint("status IN ('scheduled', 'approved', 'suspended', 'cancelled')",
                           name='ck_grade_exam_status'),
        db.CheckConstraint("verdict IS NULL OR verdict IN ('unanimous', 'majority')",
                           name='ck_grade_exam_verdict'),
        db.Index('uq_grade_exam_scheduled', 'user_program_id', unique=True,
                 postgresql_where=db.text("status = 'scheduled'"),
                 sqlite_where=db.text("status = 'scheduled'")),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_program_id = db.Column(db.Integer, db.ForeignKey('user_program.id', ondelete='CASCADE'),
                                nullable=False, index=True)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    place = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='scheduled')
    verdict = db.Column(db.String(10), nullable=True)
    honorific_mention = db.Column(db.Boolean, nullable=False, default=False)
    acta_folio = db.Column(db.String(50), nullable=True)
    held_on = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    scheduled_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_local, onupdate=now_local)

    user_program = db.relationship('UserProgram')

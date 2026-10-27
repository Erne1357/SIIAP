# app/models/grade_correction.py
from app import db
from app.utils.datetime_utils import now_local

CORRECTION_STATUSES = ('pending', 'approved', 'rejected')


class GradeCorrection(db.Model):
    """
    A teacher's request to change a final grade; postgraduate_admin decides.

    Keeps the value before and after so the kardex history stays auditable.
    At most one pending request per enrollment (enforced by the service).
    """
    __tablename__ = 'grade_correction'
    __table_args__ = (
        db.CheckConstraint("status IN ('pending', 'approved', 'rejected')",
                           name='ck_grade_correction_status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    course_enrollment_id = db.Column(
        db.Integer, db.ForeignKey('course_enrollment.id', ondelete='CASCADE'),
        nullable=False, index=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                             nullable=True)
    reason = db.Column(db.Text, nullable=False)
    old_grade = db.Column(db.SmallInteger, nullable=True)
    old_mark = db.Column(db.String(2), nullable=True)
    new_grade = db.Column(db.SmallInteger, nullable=True)
    new_mark = db.Column(db.String(2), nullable=True)
    status = db.Column(db.String(10), nullable=False, default='pending', index=True)
    decided_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                           nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)
    decision_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)

    enrollment = db.relationship('CourseEnrollment')
    requester = db.relationship('User', foreign_keys=[requested_by])

    @staticmethod
    def display(grade, mark) -> str:
        return mark or ('' if grade is None else str(grade))

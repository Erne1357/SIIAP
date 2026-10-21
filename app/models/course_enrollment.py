# app/models/course_enrollment.py
from app import db
from app.utils.datetime_utils import now_local

ENROLLMENT_STATUSES = ('enrolled', 'dropped')
#: attempt number -> type, as in TecNM's SII: ordinario, repetición, especial.
ATTEMPT_TYPES = {1: 'ordinary', 2: 'repeat', 3: 'special'}
MAX_ATTEMPTS = 3


class CourseEnrollment(db.Model):
    """
    One attempt of a student program at a subject in a period.

    This row is the kardex: phase 6B2 adds the grade to it, and history
    imported in 6B3 uses the same row with no `course_group_id`. A dropped
    attempt is kept (status 'dropped') and does not count as an attempt.
    `slot_subject_id` names the "Optativa N" slot an elective fills.
    """
    __tablename__ = 'course_enrollment'
    __table_args__ = (
        db.UniqueConstraint('user_program_id', 'subject_id', 'academic_period_id',
                            name='uq_course_enrollment_up_subject_period'),
        db.CheckConstraint("status IN ('enrolled', 'dropped')", name='ck_course_enrollment_status'),
        db.CheckConstraint('attempt BETWEEN 1 AND 3', name='ck_course_enrollment_attempt'),
        db.CheckConstraint("attempt_type IN ('ordinary', 'repeat', 'special')",
                           name='ck_course_enrollment_attempt_type'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_program_id = db.Column(db.Integer, db.ForeignKey('user_program.id', ondelete='CASCADE'),
                                nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False, index=True)
    slot_subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True,
                                index=True)
    academic_period_id = db.Column(db.Integer, db.ForeignKey('academic_period.id'),
                                   nullable=False, index=True)
    course_group_id = db.Column(db.Integer, db.ForeignKey('course_group.id', ondelete='SET NULL'),
                                nullable=True, index=True)
    attempt = db.Column(db.SmallInteger, nullable=False, default=1)
    attempt_type = db.Column(db.String(10), nullable=False, default='ordinary')
    status = db.Column(db.String(10), nullable=False, default='enrolled')
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    dropped_at = db.Column(db.DateTime, nullable=True)
    dropped_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)

    user_program = db.relationship('UserProgram')
    subject = db.relationship('Subject', foreign_keys=[subject_id])
    slot_subject = db.relationship('Subject', foreign_keys=[slot_subject_id])
    academic_period = db.relationship('AcademicPeriod')
    course_group = db.relationship('CourseGroup')

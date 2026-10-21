# app/models/course_group.py
from app import db
from app.models.mixins import PublicUUIDMixin
from app.utils.datetime_utils import now_local

GROUP_STATUSES = ('open', 'closed')


class CourseGroup(PublicUUIDMixin, db.Model):
    """
    A subject offered in an academic period: teacher, capacity, room, schedule.

    `teacher_id` may be any internal user (a coordinator who teaches
    included); viewing and grading a group depends on being its teacher, not
    on the `teacher` role. `program_id` duplicates the subject's program so
    scope checks need no join.
    """
    __tablename__ = 'course_group'
    __table_args__ = (
        db.UniqueConstraint('subject_id', 'academic_period_id', 'group_code',
                            name='uq_course_group_subject_period_code'),
        db.CheckConstraint("status IN ('open', 'closed')", name='ck_course_group_status'),
        db.CheckConstraint('capacity > 0', name='ck_course_group_capacity'),
    )

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    academic_period_id = db.Column(db.Integer, db.ForeignKey('academic_period.id'),
                                   nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False, index=True)
    group_code = db.Column(db.String(10), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                           nullable=True, index=True)
    capacity = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(120), nullable=True)
    schedule = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(10), nullable=False, default='open')
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)

    program = db.relationship('Program')
    academic_period = db.relationship('AcademicPeriod')
    subject = db.relationship('Subject')
    teacher = db.relationship('User', foreign_keys=[teacher_id])

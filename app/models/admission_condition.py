from app import db
from app.models.mixins import PublicUUIDMixin
from app.utils.datetime_utils import now_local

CONDITION_STATUSES = ('pending', 'met', 'waived')


class AdmissionCondition(PublicUUIDMixin, db.Model):
    """
    One condition of a conditional acceptance (phase 6C). A pending condition
    blocks the grade exam; `archive_id` optionally names the conclusion
    requirement that fulfils it (and then blocks reusing the admission
    document for that requirement).
    """
    __tablename__ = 'admission_condition'
    __table_args__ = (
        db.CheckConstraint("status IN ('pending', 'met', 'waived')",
                           name='ck_admission_condition_status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_program_id = db.Column(db.Integer, db.ForeignKey('user_program.id', ondelete='CASCADE'),
                                nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    archive_id = db.Column(db.Integer, db.ForeignKey('archive.id', ondelete='SET NULL'),
                           nullable=True, index=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(10), nullable=False, default='pending')
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)
    # Phase 6D: the submission whose approval met this condition automatically.
    # NULL for a condition resolved by hand; reverting that approval reopens it.
    resolved_by_submission_id = db.Column(
        db.Integer,
        db.ForeignKey('submission.id', ondelete='SET NULL',
                      name='fk_admission_condition_resolved_by_submission_id'),
        nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)

    user_program = db.relationship('UserProgram')
    archive = db.relationship('Archive')

    @property
    def is_overdue(self) -> bool:
        return (self.status == 'pending' and self.due_date is not None
                and self.due_date < now_local().date())

from app import db
from app.utils.datetime_utils import now_local

OVERRIDE_KINDS = ('not_applicable', 'accept_expired')


class ConclusionRequirementOverride(db.Model):
    """
    A coordination decision on one conclusion requirement of one student
    program (phase 6C, owner's decisions 6-7):

    - `not_applicable`: the requirement does not apply to this student; it
      counts as satisfied.
    - `accept_expired`: the reused admission document is past its validity
      (`Archive.validity_months`) and the coordination accepts it anyway.

    Removing the row undoes the decision. `reason` is mandatory.
    """
    __tablename__ = 'conclusion_requirement_override'
    __table_args__ = (
        db.UniqueConstraint('user_program_id', 'archive_id', 'kind',
                            name='uq_conclusion_requirement_override'),
        db.CheckConstraint("kind IN ('not_applicable', 'accept_expired')",
                           name='ck_conclusion_requirement_override_kind'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_program_id = db.Column(db.Integer, db.ForeignKey('user_program.id', ondelete='CASCADE'),
                                nullable=False, index=True)
    archive_id = db.Column(db.Integer, db.ForeignKey('archive.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)

    archive = db.relationship('Archive')
    creator = db.relationship('User', foreign_keys=[created_by])

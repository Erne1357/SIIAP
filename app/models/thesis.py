from app import db
from app.models.mixins import PublicUUIDMixin
from app.utils.datetime_utils import now_local

#: body -> roles it accepts (phase 6C).
MEMBER_ROLES = {
    'tutorial': ('director', 'codirector', 'advisor'),
    'exam': ('president', 'secretary', 'vocal', 'substitute'),
}
MEMBER_BODIES = tuple(MEMBER_ROLES)


class Thesis(PublicUUIDMixin, db.Model):
    """
    The thesis of one student program (phase 6C). Registered while the student
    is active; its tutorial committee and examination board are `ThesisMember`
    rows. Every change is written to the student's history by
    `conclusion_service`.
    """
    __tablename__ = 'thesis'
    __table_args__ = (
        db.UniqueConstraint('user_program_id', name='uq_thesis_user_program_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_program_id = db.Column(db.Integer, db.ForeignKey('user_program.id', ondelete='CASCADE'),
                                nullable=False)
    title = db.Column(db.String(500), nullable=False)
    research_line = db.Column(db.String(255), nullable=True)
    registered_at = db.Column(db.Date, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_local, onupdate=now_local)

    user_program = db.relationship('UserProgram')
    members = db.relationship('ThesisMember', back_populates='thesis',
                              cascade='all, delete-orphan', passive_deletes=True,
                              order_by='ThesisMember.id')

    def members_of(self, body: str) -> list:
        return [m for m in self.members if m.body == body]


class ThesisMember(db.Model):
    """
    A person on the tutorial committee (`body='tutorial'`) or the examination
    board (`body='exam'`): an internal user or an external one (name +
    institution), never both.
    """
    __tablename__ = 'thesis_member'
    __table_args__ = (
        db.CheckConstraint("body IN ('tutorial', 'exam')", name='ck_thesis_member_body'),
        db.CheckConstraint(
            "(body = 'tutorial' AND role IN ('director', 'codirector', 'advisor')) OR "
            "(body = 'exam' AND role IN ('president', 'secretary', 'vocal', 'substitute'))",
            name='ck_thesis_member_role'),
        db.CheckConstraint(
            '(user_id IS NULL) <> (external_name IS NULL)',
            name='ck_thesis_member_person'),
        db.Index('uq_thesis_member_director', 'thesis_id', unique=True,
                 postgresql_where=db.text("body = 'tutorial' AND role = 'director'"),
                 sqlite_where=db.text("body = 'tutorial' AND role = 'director'")),
        db.Index('uq_thesis_member_exam_chair', 'thesis_id', 'role', unique=True,
                 postgresql_where=db.text("body = 'exam' AND role IN ('president', 'secretary')"),
                 sqlite_where=db.text("body = 'exam' AND role IN ('president', 'secretary')")),
    )

    id = db.Column(db.Integer, primary_key=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey('thesis.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    body = db.Column(db.String(10), nullable=False)
    role = db.Column(db.String(12), nullable=False)
    # RESTRICT: deleting a user must not silently rewrite a committee or an
    # examination board (and the history that names them).
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='RESTRICT'),
                        nullable=True, index=True)
    external_name = db.Column(db.String(200), nullable=True)
    external_institution = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)

    thesis = db.relationship('Thesis', back_populates='members')
    user = db.relationship('User')

    @property
    def display_name(self) -> str:
        if self.user is not None:
            parts = (self.user.first_name, self.user.last_name, self.user.mother_last_name)
            return ' '.join(p for p in parts if p)
        return self.external_name or ''

    @property
    def is_external(self) -> bool:
        return self.user_id is None

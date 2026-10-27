"""grades_and_kardex

Revision ID: p1k2l3m4n5o6
Revises: o0j1k2l3m4n5
Create Date: 2026-10-21

Phase 6B2: grades on `course_enrollment` (draft until the acta closes),
the acta state on `course_group`, a grade-capture window per academic
period and the `grade_correction` requests.

Expand-only: nullable columns, a new table, and the enrollment status
CHECK widened with 'graded' (the previous color never writes it).
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'p1k2l3m4n5o6'
down_revision = 'o0j1k2l3m4n5'
branch_labels = None
depends_on = None


def _columns(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def _add(table, columns):
    existing = _columns(table)
    missing = [c for c in columns if c.name not in existing]
    if missing:
        with op.batch_alter_table(table) as batch:
            for column in missing:
                batch.add_column(column)


def upgrade():
    _add('academic_period', [sa.Column('grade_capture_start', sa.Date(), nullable=True),
                             sa.Column('grade_capture_end', sa.Date(), nullable=True)])
    _add('course_group', [
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('closed_by', sa.Integer(), sa.ForeignKey('user.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('capture_until', sa.Date(), nullable=True),
        sa.Column('capture_extension_reason', sa.Text(), nullable=True),
    ])
    _add('course_enrollment', [
        sa.Column('grade', sa.SmallInteger(), nullable=True),
        sa.Column('grade_mark', sa.String(2), nullable=True),
        sa.Column('result', sa.String(10), nullable=True),
        sa.Column('graded_at', sa.DateTime(), nullable=True),
        sa.Column('graded_by', sa.Integer(), sa.ForeignKey('user.id', ondelete='SET NULL'),
                  nullable=True),
    ])

    checks = _checks('course_enrollment')
    with op.batch_alter_table('course_enrollment') as batch:
        if 'ck_course_enrollment_status' in checks:
            batch.drop_constraint('ck_course_enrollment_status', type_='check')
        batch.create_check_constraint('ck_course_enrollment_status',
                                      "status IN ('enrolled', 'dropped', 'graded')")
        if 'ck_course_enrollment_grade' not in checks:
            batch.create_check_constraint('ck_course_enrollment_grade', 'grade BETWEEN 0 AND 100')
        if 'ck_course_enrollment_grade_mark' not in checks:
            batch.create_check_constraint(
                'ck_course_enrollment_grade_mark',
                "grade_mark IS NULL OR (grade_mark = 'NP' AND grade IS NULL)")
        if 'ck_course_enrollment_result' not in checks:
            batch.create_check_constraint('ck_course_enrollment_result',
                                          "result IS NULL OR result IN ('passed', 'failed')")

    if 'grade_correction' not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            'grade_correction',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('course_enrollment_id', sa.Integer(),
                      sa.ForeignKey('course_enrollment.id', ondelete='CASCADE'), nullable=False),
            sa.Column('requested_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reason', sa.Text(), nullable=False),
            sa.Column('old_grade', sa.SmallInteger(), nullable=True),
            sa.Column('old_mark', sa.String(2), nullable=True),
            sa.Column('new_grade', sa.SmallInteger(), nullable=True),
            sa.Column('new_mark', sa.String(2), nullable=True),
            sa.Column('status', sa.String(10), nullable=False),
            sa.Column('decided_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.Column('decided_at', sa.DateTime(), nullable=True),
            sa.Column('decision_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')",
                               name='ck_grade_correction_status'),
        )
        op.create_index('ix_grade_correction_course_enrollment_id', 'grade_correction',
                        ['course_enrollment_id'])
        op.create_index('ix_grade_correction_status', 'grade_correction', ['status'])


def downgrade():
    if 'grade_correction' in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table('grade_correction')
    # Graded rows cannot satisfy the narrower CHECK: they go back to 'enrolled'
    # (their grades disappear with the columns below).
    op.execute("UPDATE course_enrollment SET status = 'enrolled' WHERE status = 'graded'")
    checks = _checks('course_enrollment')
    with op.batch_alter_table('course_enrollment') as batch:
        for name in ('ck_course_enrollment_grade', 'ck_course_enrollment_grade_mark',
                     'ck_course_enrollment_result', 'ck_course_enrollment_status'):
            if name in checks:
                batch.drop_constraint(name, type_='check')
        batch.create_check_constraint('ck_course_enrollment_status',
                                      "status IN ('enrolled', 'dropped')")
    for table, names in (
        ('course_enrollment', ('graded_by', 'graded_at', 'result', 'grade_mark', 'grade')),
        ('course_group', ('capture_extension_reason', 'capture_until', 'closed_by', 'closed_at')),
        ('academic_period', ('grade_capture_end', 'grade_capture_start')),
    ):
        existing = _columns(table)
        with op.batch_alter_table(table) as batch:
            for name in names:
                if name in existing:
                    batch.drop_column(name)

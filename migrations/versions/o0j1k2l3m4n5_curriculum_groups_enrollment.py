"""curriculum_groups_enrollment

Revision ID: o0j1k2l3m4n5
Revises: n9i0j1k2l3m4
Create Date: 2026-10-21

Phase 6B1: versioned study plans, course groups per period and the course
enrollment row that phase 6B2 will grade (one row per attempt).

1. Tables `curriculum_plan`, `subject`, `course_group`, `course_enrollment`.
2. `user_program.curriculum_plan_id` (FK SET NULL, indexed).
3. Role `teacher`.
4. Backfill: version 1 (current) of every program from `curriculum_structure`
   (both shapes the model normalizes); a subject named "Optativa ..." becomes
   an `elective_slot`; key/credits stay NULL for the owner to complete. Every
   user_program of the program is tied to version 1.

Expand-only: new tables and a nullable column, so the previous color keeps
serving during the blue-green switch.
"""
import json
import re

import sqlalchemy as sa
from alembic import op

from app.utils.datetime_utils import now_local


# revision identifiers, used by Alembic.
revision = 'o0j1k2l3m4n5'
down_revision = 'n9i0j1k2l3m4'
branch_labels = None
depends_on = None

ELECTIVE_SLOT = re.compile(r'^\s*optativa\b', re.IGNORECASE)


def curriculum_rows(structure) -> list[dict]:
    """
    Flatten `curriculum_structure` into subject rows.

    Mirrors `Program.curriculum_semesters`: semesters as {semester, courses}
    or {number, name, subjects}; courses as dicts or bare names.
    """
    if not isinstance(structure, dict) or not isinstance(structure.get('semesters'), list):
        return []
    rows = []
    for index, raw in enumerate(structure['semesters']):
        if not isinstance(raw, dict):
            continue
        number = raw.get('semester')
        if not isinstance(number, int) or number <= 0:
            number = raw.get('number')
        if not isinstance(number, int) or number <= 0:
            number = index + 1
        items = raw.get('courses') or raw.get('subjects') or []
        for item in items:
            if isinstance(item, str):
                name, code, credits = item.strip(), None, None
            elif isinstance(item, dict):
                name = (item.get('name') or item.get('code') or '').strip()
                code, credits = item.get('code'), item.get('credits')
            else:
                continue
            if not name:
                continue
            rows.append({
                'name': name[:200],
                'key': (str(code).strip()[:20] or None) if code else None,
                'credits': credits if isinstance(credits, int) and 0 <= credits <= 99 else None,
                'suggested_semester': number if number <= 20 else None,
                'kind': 'elective_slot' if ELECTIVE_SLOT.match(name) else 'required',
            })
    return rows


def backfill_curriculum_plans(conn) -> dict:
    """Create version 1 for programs without a plan and tie their user programs to it."""
    counts = {'programs': 0, 'subjects': 0, 'slots': 0, 'user_programs': 0}
    programs = conn.execute(sa.text(
        "SELECT p.id, p.name, p.curriculum_structure FROM program p "
        "WHERE NOT EXISTS (SELECT 1 FROM curriculum_plan c WHERE c.program_id = p.id)"
    )).fetchall()
    for program_id, name, structure in programs:
        if isinstance(structure, str):
            try:
                structure = json.loads(structure)
            except ValueError:
                structure = None
        conn.execute(sa.text(
            "INSERT INTO curriculum_plan (program_id, version, name, is_current, created_at) "
            "VALUES (:program_id, 1, :name, :current, :now)"
        ), {'program_id': program_id, 'name': f'Plan {name}'[:120], 'current': True,
            'now': now_local()})
        plan_id = conn.execute(sa.text(
            "SELECT id FROM curriculum_plan WHERE program_id = :p AND version = 1"
        ), {'p': program_id}).scalar()
        seen_keys = set()
        for sequence, row in enumerate(curriculum_rows(structure), start=1):
            if row['key'] in seen_keys:
                row['key'] = None
            if row['key']:
                seen_keys.add(row['key'])
            conn.execute(sa.text(
                "INSERT INTO subject (plan_id, key, name, credits, suggested_semester, kind, "
                "sequence, is_active) VALUES (:plan_id, :key, :name, :credits, "
                ":suggested_semester, :kind, :sequence, :active)"
            ), {**row, 'plan_id': plan_id, 'sequence': sequence, 'active': True})
            counts['subjects'] += 1
            counts['slots'] += row['kind'] == 'elective_slot'
        result = conn.execute(sa.text(
            "UPDATE user_program SET curriculum_plan_id = :plan "
            "WHERE program_id = :p AND curriculum_plan_id IS NULL"
        ), {'plan': plan_id, 'p': program_id})
        counts['user_programs'] += result.rowcount or 0
        counts['programs'] += 1
    return counts


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade():
    tables = _tables()
    if 'curriculum_plan' not in tables:
        op.create_table(
            'curriculum_plan',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('program_id', sa.Integer(),
                      sa.ForeignKey('program.id', ondelete='CASCADE'), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('is_current', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('created_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.UniqueConstraint('program_id', 'version', name='uq_curriculum_plan_program_version'),
        )
        op.create_index('ix_curriculum_plan_program_id', 'curriculum_plan', ['program_id'])
        # At most one current version per program, enforced by the database.
        op.create_index('uq_curriculum_plan_one_current', 'curriculum_plan', ['program_id'],
                        unique=True, postgresql_where=sa.text('is_current'),
                        sqlite_where=sa.text('is_current'))
    if 'subject' not in tables:
        op.create_table(
            'subject',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('plan_id', sa.Integer(),
                      sa.ForeignKey('curriculum_plan.id', ondelete='CASCADE'), nullable=False),
            sa.Column('key', sa.String(20), nullable=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('credits', sa.Integer(), nullable=True),
            sa.Column('suggested_semester', sa.Integer(), nullable=True),
            sa.Column('kind', sa.String(20), nullable=False),
            sa.Column('sequence', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.UniqueConstraint('plan_id', 'key', name='uq_subject_plan_key'),
            sa.CheckConstraint("kind IN ('required', 'elective_slot', 'elective')",
                               name='ck_subject_kind'),
        )
        op.create_index('ix_subject_plan_id', 'subject', ['plan_id'])
    if 'course_group' not in tables:
        op.create_table(
            'course_group',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('uuid', sa.Uuid(as_uuid=True), nullable=False),
            sa.Column('program_id', sa.Integer(),
                      sa.ForeignKey('program.id', ondelete='CASCADE'), nullable=False),
            sa.Column('academic_period_id', sa.Integer(),
                      sa.ForeignKey('academic_period.id'), nullable=False),
            sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subject.id'), nullable=False),
            sa.Column('group_code', sa.String(10), nullable=False),
            sa.Column('teacher_id', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.Column('capacity', sa.Integer(), nullable=False),
            sa.Column('location', sa.String(120), nullable=True),
            sa.Column('schedule', sa.Text(), nullable=True),
            sa.Column('status', sa.String(10), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('created_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.UniqueConstraint('subject_id', 'academic_period_id', 'group_code',
                                name='uq_course_group_subject_period_code'),
            sa.CheckConstraint("status IN ('open', 'closed')", name='ck_course_group_status'),
            sa.CheckConstraint('capacity > 0', name='ck_course_group_capacity'),
        )
        op.create_index('ix_course_group_uuid', 'course_group', ['uuid'], unique=True)
        for column in ('program_id', 'academic_period_id', 'subject_id', 'teacher_id'):
            op.create_index(f'ix_course_group_{column}', 'course_group', [column])
    if 'course_enrollment' not in tables:
        op.create_table(
            'course_enrollment',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_program_id', sa.Integer(),
                      sa.ForeignKey('user_program.id', ondelete='CASCADE'), nullable=False),
            sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subject.id'), nullable=False),
            sa.Column('slot_subject_id', sa.Integer(), sa.ForeignKey('subject.id'), nullable=True),
            sa.Column('academic_period_id', sa.Integer(),
                      sa.ForeignKey('academic_period.id'), nullable=False),
            sa.Column('course_group_id', sa.Integer(),
                      sa.ForeignKey('course_group.id', ondelete='SET NULL'), nullable=True),
            sa.Column('attempt', sa.SmallInteger(), nullable=False),
            sa.Column('attempt_type', sa.String(10), nullable=False),
            sa.Column('status', sa.String(10), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('created_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.Column('dropped_at', sa.DateTime(), nullable=True),
            sa.Column('dropped_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.UniqueConstraint('user_program_id', 'subject_id', 'academic_period_id',
                                name='uq_course_enrollment_up_subject_period'),
            sa.CheckConstraint("status IN ('enrolled', 'dropped')",
                               name='ck_course_enrollment_status'),
            sa.CheckConstraint('attempt BETWEEN 1 AND 3', name='ck_course_enrollment_attempt'),
            sa.CheckConstraint("attempt_type IN ('ordinary', 'repeat', 'special')",
                               name='ck_course_enrollment_attempt_type'),
        )
        for column in ('user_program_id', 'subject_id', 'slot_subject_id',
                       'academic_period_id', 'course_group_id'):
            op.create_index(f'ix_course_enrollment_{column}', 'course_enrollment', [column])

    up_columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('user_program')}
    if 'curriculum_plan_id' not in up_columns:
        with op.batch_alter_table('user_program') as batch:
            batch.add_column(sa.Column('curriculum_plan_id', sa.Integer(), nullable=True))
            batch.create_foreign_key('fk_user_program_curriculum_plan_id', 'curriculum_plan',
                                     ['curriculum_plan_id'], ['id'], ondelete='SET NULL')
            batch.create_index('ix_user_program_curriculum_plan_id', ['curriculum_plan_id'])

    op.execute(
        "INSERT INTO role (name, description) "
        "SELECT 'teacher', 'Docente: imparte y califica sus grupos' "
        "WHERE NOT EXISTS (SELECT 1 FROM role WHERE name = 'teacher')"
    )

    counts = backfill_curriculum_plans(op.get_bind())
    print(f'curriculum backfill: {counts}')


def downgrade():
    up_columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('user_program')}
    if 'curriculum_plan_id' in up_columns:
        with op.batch_alter_table('user_program') as batch:
            batch.drop_index('ix_user_program_curriculum_plan_id')
            batch.drop_constraint('fk_user_program_curriculum_plan_id', type_='foreignkey')
            batch.drop_column('curriculum_plan_id')
    tables = _tables()
    for table in ('course_enrollment', 'course_group', 'subject', 'curriculum_plan'):
        if table in tables:
            op.drop_table(table)
    # A teacher account keeps working only while the role exists; drop the
    # role only when nobody holds it.
    unused = ("SELECT r.id FROM role r WHERE r.name = 'teacher' AND NOT EXISTS "
              "(SELECT 1 FROM \"user\" u WHERE u.role_id = r.id)")
    for table in ('role_permission', 'role_permission_override'):
        if table in tables:
            op.execute(f"DELETE FROM {table} WHERE role_id IN ({unused})")
    op.execute(f"DELETE FROM role WHERE id IN ({unused})")

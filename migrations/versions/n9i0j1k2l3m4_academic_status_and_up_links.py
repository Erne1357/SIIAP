"""academic_status_and_up_links

Revision ID: n9i0j1k2l3m4
Revises: m8h9i0j1k2l3
Create Date: 2026-10-21

Phase 6A: an enrolled student's trajectory gets its own state, and documents
and history get tied to the student program instead of the user alone.

1. `user_program.academic_status` (+ changed_at, graduated_at, withdrawn_at,
   withdrawal_reason) and CHECK `ck_user_program_academic_status`. NULL until
   the program is `enrolled`; admission_status is untouched.
2. `user_program_id` (FK SET NULL, indexed) on `submission`,
   `extension_request` and `user_history`.
3. Backfill:
   - academic_status of every `enrolled` row from its semester enrollments:
     latest one `dropped` -> withdrawn, `on_leave` -> on_leave, a `completed`
     one at or past the plan length -> graduated (date = end of that period,
     the same rule retention used), otherwise active.
   - submission / extension_request.user_program_id from the user's program
     that owns `program_step`. No match stays NULL.

Expand-only: new nullable columns, so the previous color keeps serving during
the blue-green switch. Column creation is skipped when it already exists.
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'n9i0j1k2l3m4'
down_revision = 'm8h9i0j1k2l3'
branch_labels = None
depends_on = None


ACADEMIC_STATUSES = ('active', 'on_leave', 'withdrawn', 'graduated')
LINKED_TABLES = ('submission', 'extension_request', 'user_history')

UP_COLUMNS = (
    ('academic_status', sa.String(20)),
    ('academic_status_changed_at', sa.DateTime()),
    ('graduated_at', sa.Date()),
    ('withdrawn_at', sa.DateTime()),
    ('withdrawal_reason', sa.Text()),
)


def _columns(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def backfill_academic_status(conn) -> dict:
    """Set academic_status on enrolled rows that have none. Returns counts per status."""
    ups = conn.execute(sa.text(
        "SELECT up.id, p.duration_semesters FROM user_program up "
        "JOIN program p ON p.id = up.program_id "
        "WHERE up.admission_status = 'enrolled' AND up.academic_status IS NULL"
    )).fetchall()
    counts = {s: 0 for s in ACADEMIC_STATUSES}
    for up_id, duration in ups:
        rows = conn.execute(sa.text(
            "SELECT se.status, se.semester_number, se.updated_at, ap.end_date "
            "FROM semester_enrollment se "
            "LEFT JOIN academic_period ap ON ap.id = se.academic_period_id "
            "WHERE se.user_program_id = :up "
            # NULL periods last on both engines (PostgreSQL puts them first in DESC).
            "ORDER BY CASE WHEN ap.start_date IS NULL THEN 1 ELSE 0 END, "
            "ap.start_date DESC, se.id DESC"
        ), {'up': up_id}).fetchall()
        values = {'withdrawn_at': None, 'withdrawal_reason': None, 'graduated_at': None}
        latest = rows[0] if rows else None
        finished = [r for r in rows if r[0] == 'completed'
                    and duration and (r[1] or 0) >= duration]
        if latest is not None and latest[0] == 'dropped':
            status = 'withdrawn'
            values['withdrawn_at'] = latest[2]
            values['withdrawal_reason'] = 'Baja definitiva registrada antes de la fase 6A.'
        elif latest is not None and latest[0] == 'on_leave':
            status = 'on_leave'
        elif finished and latest[0] == 'completed':
            status = 'graduated'
            values['graduated_at'] = finished[0][3]
        else:
            status = 'active'
        conn.execute(sa.text(
            "UPDATE user_program SET academic_status = :status, "
            "withdrawn_at = :withdrawn_at, withdrawal_reason = :withdrawal_reason, "
            "graduated_at = :graduated_at WHERE id = :id"
        ), {'status': status, 'id': up_id, **values})
        counts[status] += 1
    return counts


def backfill_user_program_links(conn) -> dict:
    """Fill user_program_id on submission / extension_request. Returns NULLs left per table."""
    left = {}
    for table in ('submission', 'extension_request'):
        conn.execute(sa.text(
            f"UPDATE {table} SET user_program_id = ("
            "  SELECT up.id FROM user_program up "
            "  JOIN program_step ps ON ps.program_id = up.program_id "
            f"  WHERE ps.id = {table}.program_step_id AND up.user_id = {table}.user_id"
            ") WHERE user_program_id IS NULL"
        ))
        left[table] = conn.execute(sa.text(
            f"SELECT COUNT(*) FROM {table} WHERE user_program_id IS NULL"
        )).scalar()
    return left


def upgrade():
    existing = _columns('user_program')
    with op.batch_alter_table('user_program') as batch:
        for name, type_ in UP_COLUMNS:
            if name not in existing:
                batch.add_column(sa.Column(name, type_, nullable=True))
        if 'ck_user_program_academic_status' not in _checks('user_program'):
            allowed = ', '.join(f"'{s}'" for s in ACADEMIC_STATUSES)
            batch.create_check_constraint(
                'ck_user_program_academic_status', f'academic_status IN ({allowed})')

    for table in LINKED_TABLES:
        if 'user_program_id' in _columns(table):
            continue
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('user_program_id', sa.Integer(), nullable=True))
            batch.create_foreign_key(
                f'fk_{table}_user_program_id', 'user_program',
                ['user_program_id'], ['id'], ondelete='SET NULL')
            batch.create_index(f'ix_{table}_user_program_id', ['user_program_id'])

    conn = op.get_bind()
    counts = backfill_academic_status(conn)
    left = backfill_user_program_links(conn)
    print(f'academic_status backfill: {counts}; user_program_id NULL left: {left}')


def downgrade():
    for table in LINKED_TABLES:
        if 'user_program_id' not in _columns(table):
            continue
        inspector = sa.inspect(op.get_bind())
        indexes = {i['name'] for i in inspector.get_indexes(table)}
        fks = {f['name'] for f in inspector.get_foreign_keys(table)}
        with op.batch_alter_table(table) as batch:
            if f'ix_{table}_user_program_id' in indexes:
                batch.drop_index(f'ix_{table}_user_program_id')
            if f'fk_{table}_user_program_id' in fks:
                batch.drop_constraint(f'fk_{table}_user_program_id', type_='foreignkey')
            batch.drop_column('user_program_id')
    existing = _columns('user_program')
    with op.batch_alter_table('user_program') as batch:
        if 'ck_user_program_academic_status' in _checks('user_program'):
            batch.drop_constraint('ck_user_program_academic_status', type_='check')
        for name, _ in reversed(UP_COLUMNS):
            if name in existing:
                batch.drop_column(name)

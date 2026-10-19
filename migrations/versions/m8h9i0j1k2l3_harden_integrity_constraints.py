"""harden_integrity_constraints

Revision ID: m8h9i0j1k2l3
Revises: l7g8h9i0j1k2
Create Date: 2026-10-19

Puts back the business rules the database was not enforcing.

1. `uq_semester_enrollment_up_period` — one enrollment per student program and
   academic period. Revision `8f4h5i6j7k8l` created it; autogenerate silently
   dropped it in `135a97882bf7` because the model never declared it. Since
   then every "already enrolled?" check was read-then-write, so a double click
   could create two rows for the same semester.
2. `uq_user_program_user_program` — a user holds a given program once. A user
   MAY hold several programs (master's graduate applying to a doctorate), so
   the rule is on the pair, never on `user_id` alone.
3. CHECK constraints for `user_program.admission_status` and
   `semester_enrollment.status`. The allowed sets used to live only in
   comments; a typo in a service wrote an unknown state nobody could see.
4. Indexes on the foreign keys used for lookups and joins. PostgreSQL does not
   index a FK column on its own. Audit-only columns (`created_by`,
   `decided_by`, …) stay unindexed on purpose: nothing filters by them.

Expand-only: no column changes type or disappears, so the previous color keeps
serving against the new schema during the blue-green switch. Every statement
is idempotent (`IF NOT EXISTS` / catalog checks).

Duplicates are NOT deleted here. Which of two enrollment rows is the right one
is a human decision (it may own a payment proof), so the upgrade stops with
the offending ids instead, and the pg_dump taken by the deploy is untouched.
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'm8h9i0j1k2l3'
down_revision = 'l7g8h9i0j1k2'
branch_labels = None
depends_on = None


ADMISSION_STATUSES = (
    'in_progress', 'interview_completed', 'deliberation', 'accepted',
    'rejected', 'deferred', 'enrolled', 'expired',
)
ENROLLMENT_STATUSES = ('pending', 'active', 'completed', 'on_leave', 'dropped')

UNIQUES = (
    # (table, name, columns)
    ('semester_enrollment', 'uq_semester_enrollment_up_period',
     ('user_program_id', 'academic_period_id')),
    ('user_program', 'uq_user_program_user_program', ('user_id', 'program_id')),
)

CHECKS = (
    # (table, name, column, allowed values)
    ('user_program', 'ck_user_program_admission_status', 'admission_status',
     ADMISSION_STATUSES),
    ('semester_enrollment', 'ck_semester_enrollment_status', 'status',
     ENROLLMENT_STATUSES),
)

#: Lookup/join foreign keys that get an index (`ix_<table>_<column>`).
FK_INDEXES = (
    ('acceptance_document', 'user_program_id'),
    ('appointment', 'applicant_id'),
    ('appointment', 'event_id'),
    ('appointment_change_request', 'appointment_id'),
    ('archive', 'step_id'),
    ('document_deadline', 'academic_period_id'),
    ('document_deadline', 'archive_id'),
    ('document_deadline', 'program_id'),
    ('document_mapping', 'from_archive_id'),
    ('document_mapping', 'from_program_id'),
    ('document_mapping', 'to_archive_id'),
    ('document_mapping', 'to_program_id'),
    ('document_template', 'program_id'),
    ('email_queue', 'notification_id'),
    ('email_queue', 'user_id'),
    ('enrollment_deferral', 'deferred_to_period_id'),
    ('enrollment_deferral', 'original_period_id'),
    ('enrollment_deferral', 'user_program_id'),
    ('event', 'academic_period_id'),
    ('event', 'program_id'),
    ('event_attendance', 'event_id'),
    ('event_attendance', 'user_id'),
    ('event_host', 'event_id'),
    ('event_host', 'user_id'),
    ('event_image', 'event_id'),
    ('event_invitation', 'event_id'),
    ('event_invitation', 'user_id'),
    ('event_reminder_log', 'appointment_id'),
    ('event_reminder_log', 'user_id'),
    ('event_slot', 'event_window_id'),
    ('event_window', 'event_id'),
    ('extension_request', 'archive_id'),
    ('extension_request', 'program_step_id'),
    ('extension_request', 'user_id'),
    ('notification', 'related_invitation_id'),
    ('notification', 'user_id'),
    ('program', 'coordinator_id'),
    ('program_admission_interest', 'period_id'),
    ('program_change_request', 'applicant_id'),
    ('program_change_request', 'from_program_id'),
    ('program_change_request', 'to_program_id'),
    ('program_step', 'program_id'),
    ('program_step', 'step_id'),
    ('purge_run', 'program_id'),
    ('retention_policy', 'archive_id'),
    ('role_permission', 'permission_id'),
    ('role_permission_override', 'permission_id'),
    ('role_permission_override', 'role_id'),
    ('semester_enrollment', 'academic_period_id'),
    ('step', 'phase_id'),
    ('submission', 'academic_period_id'),
    ('submission', 'archive_id'),
    ('submission', 'document_deadline_id'),
    ('submission', 'program_step_id'),
    ('submission', 'user_id'),
    ('user', 'role_id'),
    ('user_history', 'admin_id'),
    ('user_history', 'user_id'),
    ('user_permission', 'permission_id'),
    ('user_permission', 'program_id'),
    ('user_program', 'admission_period_id'),
    ('user_program', 'program_id'),
)


def _q(name):
    """Quote an identifier (`user` is a reserved word in PostgreSQL)."""
    return '"' + name.replace('"', '""') + '"'


def _constraint_exists(conn, name):
    return conn.execute(
        sa.text('SELECT 1 FROM pg_constraint WHERE conname = :n'), {'n': name}
    ).first() is not None


def _assert_no_duplicates(conn, table, columns):
    cols = ', '.join(_q(c) for c in columns)
    rows = conn.execute(sa.text(
        f'SELECT {cols}, array_agg(id ORDER BY id) AS ids FROM {_q(table)} '
        f'GROUP BY {cols} HAVING count(*) > 1'
    )).all()
    if rows:
        detail = '\n'.join(f'  {tuple(r[:-1])} -> ids {list(r[-1])}' for r in rows)
        raise RuntimeError(
            f'{table} tiene filas duplicadas en ({", ".join(columns)}).\n'
            f'Resuelve cada grupo a mano (conserva la fila correcta) y repite la migración:\n'
            f'{detail}'
        )


def _assert_known_values(conn, table, column, allowed):
    unknown = conn.execute(
        sa.text(
            f'SELECT DISTINCT {_q(column)} FROM {_q(table)} '
            f'WHERE NOT ({_q(column)} = ANY(:allowed))'
        ),
        {'allowed': list(allowed)},
    ).scalars().all()
    if unknown:
        raise RuntimeError(
            f'{table}.{column} contiene valores fuera del catálogo: {unknown}. '
            f'Corrígelos o añádelos al catálogo antes de migrar.'
        )


def upgrade():
    conn = op.get_bind()

    for table, name, columns in UNIQUES:
        if _constraint_exists(conn, name):
            continue
        _assert_no_duplicates(conn, table, columns)
        op.create_unique_constraint(name, table, list(columns))

    for table, name, column, allowed in CHECKS:
        if _constraint_exists(conn, name):
            continue
        _assert_known_values(conn, table, column, allowed)
        values = ', '.join(f"'{v}'" for v in allowed)
        op.create_check_constraint(name, table, f'{column} IN ({values})')

    for table, column in FK_INDEXES:
        op.execute(
            f'CREATE INDEX IF NOT EXISTS {_q(f"ix_{table}_{column}")} '
            f'ON {_q(table)} ({_q(column)})'
        )


def downgrade():
    for table, column in reversed(FK_INDEXES):
        op.execute(f'DROP INDEX IF EXISTS {_q(f"ix_{table}_{column}")}')
    for table, name, _column, _allowed in reversed(CHECKS):
        op.execute(f'ALTER TABLE {_q(table)} DROP CONSTRAINT IF EXISTS {_q(name)}')
    for table, name, _columns in reversed(UNIQUES):
        op.execute(f'ALTER TABLE {_q(table)} DROP CONSTRAINT IF EXISTS {_q(name)}')

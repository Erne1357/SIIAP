"""leave request archive key

Revision ID: u6p7q8r9s0t1
Revises: t5o6p7q8r9s0
Create Date: 2026-10-27

Data only. The temporary-leave flow finds its archive by
`archive_key = 'leave_request'` (`permanence_service._get_leave_request_archive`)
and the review engine classifies a submission as a leave request by that same
key (`review_engine.submission_kinds.kind_key_for_submission`). The key was
only ever set by a manual script (`database/DML/archives/01_archive_keys.sql`),
and the production copy has it NULL on "Solicitud de Baja Temporal": leave
requests would be listed as permanence documents and approving one would skip
the leave effects (semester enrollment and student program `on_leave`).

Idempotent: when an archive already carries the key nothing is done. Otherwise
the candidate is an ACTIVE, unkeyed archive of a `permanence` phase step whose
name contains "baja temporal" (case-insensitive) — the same rule as the manual
script; the exact name "Solicitud de Baja Temporal" wins if several match.
No candidate, or an ambiguous one, is a no-op with a printed notice.

Downgrade: no-op (the key is the correct state; removing it would break the
leave flow).
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'u6p7q8r9s0t1'
down_revision = 't5o6p7q8r9s0'
branch_labels = None
depends_on = None


LEAVE_KEY = 'leave_request'
LEAVE_ARCHIVE_NAME = 'Solicitud de Baja Temporal'


def backfill_leave_request_key(conn):
    """Set the key on the leave-request archive. Returns its id, or None when nothing changed."""
    taken = conn.execute(sa.text(
        'SELECT COUNT(*) FROM archive WHERE archive_key = :key'), {'key': LEAVE_KEY}).scalar()
    if taken:
        print(f"[u6p7q8r9s0t1] archive_key '{LEAVE_KEY}' already set; nothing to do.")
        return None

    rows = conn.execute(sa.text(
        'SELECT a.id, a.name FROM archive a '
        'JOIN step s ON s.id = a.step_id '
        'JOIN phase p ON p.id = s.phase_id '
        "WHERE p.name = 'permanence' AND a.is_active = :yes "
        'AND a.archive_key IS NULL '
        "AND LOWER(a.name) LIKE '%baja temporal%' "
        'ORDER BY a.id'
    ), {'yes': True}).fetchall()

    exact = [row for row in rows if row[1] == LEAVE_ARCHIVE_NAME]
    if len(exact) == 1:
        chosen = exact[0]
    elif len(rows) == 1:
        chosen = rows[0]
    else:
        print(f"[u6p7q8r9s0t1] NOTICE: {len(rows)} candidate archive(s) for "
              f"'{LEAVE_KEY}'; none keyed. Set it by hand.")
        return None

    conn.execute(sa.text('UPDATE archive SET archive_key = :key WHERE id = :id'),
                 {'key': LEAVE_KEY, 'id': chosen[0]})
    print(f"[u6p7q8r9s0t1] archive {chosen[0]} ('{chosen[1]}') keyed as '{LEAVE_KEY}'.")
    return chosen[0]


def upgrade():
    backfill_leave_request_key(op.get_bind())


def downgrade():
    pass

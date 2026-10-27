"""Database probes behind the liveness / readiness endpoints."""
from __future__ import annotations

from app import db


def database_ok() -> bool:
    """True when the database takes a trivial query."""
    try:
        db.session.execute(db.text('SELECT 1'))
        return True
    except Exception:
        # A failed statement leaves the scoped session in an aborted
        # transaction; without the rollback every later request on this
        # thread fails too, and the probe would report its own damage.
        db.session.rollback()
        return False


def database_revisions() -> frozenset | None:
    """Alembic revision(s) stamped in the database, or None when unreadable."""
    try:
        rows = db.session.execute(db.text('SELECT version_num FROM alembic_version')).all()
        return frozenset(r[0] for r in rows)
    except Exception:
        db.session.rollback()
        return None

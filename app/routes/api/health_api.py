"""
Liveness and readiness endpoints.

GET /health  →  liveness: the process answers and the database takes a query.
                Docker uses it to restart a wedged container.
GET /ready   →  readiness: everything a request needs is reachable AND the
                database schema is exactly the one this image was built for.
                The blue-green deploy only points nginx at a color whose
                /ready answers 200.
"""

from functools import lru_cache
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from app import db

api_health = Blueprint('api_health', __name__)

_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / 'migrations'


def _database_ok() -> bool:
    try:
        db.session.execute(db.text('SELECT 1'))
        return True
    except Exception:
        # A failed statement leaves the scoped session in an aborted
        # transaction; without the rollback every later request on this
        # thread fails too, and the probe would report its own damage.
        db.session.rollback()
        return False


def _redis_ok() -> bool:
    try:
        import redis
        url = current_app.config.get('REDIS_URL', 'redis://redis:6379/0')
        client = redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        return bool(client.ping())
    except Exception:
        return False


@lru_cache(maxsize=1)
def code_migration_heads() -> frozenset:
    """Alembic head revision(s) shipped in this image."""
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory

    cfg = AlembicConfig()
    cfg.set_main_option('script_location', str(_MIGRATIONS_DIR))
    return frozenset(ScriptDirectory.from_config(cfg).get_heads())


def _database_revisions() -> frozenset | None:
    try:
        rows = db.session.execute(db.text('SELECT version_num FROM alembic_version')).all()
        return frozenset(r[0] for r in rows)
    except Exception:
        db.session.rollback()
        return None


@api_health.route('/health', methods=['GET'])
def health_check():
    """Liveness: la app y la base de datos responden."""
    db_ok = _database_ok()
    status = 'ok' if db_ok else 'degraded'
    return jsonify({'status': status, 'db': db_ok}), 200 if db_ok else 503


@api_health.route('/ready', methods=['GET'])
def readiness_check():
    """Readiness: DB, Redis y esquema al día con esta imagen."""
    db_ok = _database_ok()
    redis_ok = _redis_ok()
    heads = code_migration_heads()
    revisions = _database_revisions() if db_ok else None
    schema_ok = revisions is not None and revisions == heads

    ready = db_ok and redis_ok and schema_ok
    body = {
        'status': 'ready' if ready else 'not_ready',
        'db': db_ok,
        'redis': redis_ok,
        'schema': schema_ok,
        'code_heads': sorted(heads),
        'db_revisions': sorted(revisions) if revisions is not None else None,
        'version': current_app.config.get('STATIC_VERSION'),
    }
    return jsonify(body), 200 if ready else 503

"""Migration s4n5o6p7q8r9: admission_condition.resolved_by_submission_id (expand-only)."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app import db

MIGRATION = (Path(__file__).resolve().parents[2] / 'migrations' / 'versions'
             / 's4n5o6p7q8r9_condition_resolved_by_submission.py')


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location('mig_s4n5', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _columns(conn):
    return {c['name'] for c in sa.inspect(conn).get_columns('admission_condition')}


def _run(step):
    with db.engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            step()
        return _columns(conn)


def test_revision_chain(migration):
    assert migration.revision == 's4n5o6p7q8r9'
    assert migration.down_revision == 'r3m4n5o6p7q8'


def test_downgrade_and_upgrade_are_idempotent(app, migration):
    db.session.remove()
    with db.engine.connect() as conn:
        assert 'resolved_by_submission_id' in _columns(conn)

    assert 'resolved_by_submission_id' not in _run(migration.downgrade)
    assert 'resolved_by_submission_id' not in _run(migration.downgrade)
    assert 'resolved_by_submission_id' in _run(migration.upgrade)
    assert 'resolved_by_submission_id' in _run(migration.upgrade)

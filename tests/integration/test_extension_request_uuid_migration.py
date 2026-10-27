"""Migration t5o6p7q8r9s0: extension_request.uuid (blue-green safe expand)."""

import importlib.util
from datetime import timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app import db
from app.models import Archive, ExtensionRequest, Phase, ProgramStep, Step
from app.utils.datetime_utils import now_local
from tests.support.factories import make_program, make_user

MIGRATION = (Path(__file__).resolve().parents[2] / 'migrations' / 'versions'
             / 't5o6p7q8r9s0_extension_request_uuid.py')


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location('mig_t5o6', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _columns(conn):
    return {c['name'] for c in sa.inspect(conn).get_columns('extension_request')}


def _run(step):
    with db.engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            step()
        return _columns(conn)


def test_revision_chain(migration):
    assert migration.revision == 't5o6p7q8r9s0'
    assert migration.down_revision == 's4n5o6p7q8r9'


def test_downgrade_and_upgrade_are_idempotent_and_backfill(app, migration):
    coord = make_user('program_admin')
    program = make_program(coord)
    student = make_user('student')
    phase = Phase(name='admission', description='a')
    db.session.add(phase)
    db.session.flush()
    step = Step(name='s', description='s', phase_id=phase.id)
    db.session.add(step)
    db.session.flush()
    ps = ProgramStep(sequence=1, program_id=program.id, step_id=step.id)
    archive = Archive(name='a', description='a', file_path=None, step_id=step.id)
    db.session.add_all([ps, archive])
    db.session.flush()
    er = ExtensionRequest(user_id=student.id, archive_id=archive.id, program_step_id=ps.id,
                          requested_by=student.id, reason='r',
                          requested_until=now_local().replace(tzinfo=None) + timedelta(days=3))
    db.session.add(er)
    db.session.commit()
    er_id = er.id
    db.session.remove()

    assert 'uuid' not in _run(migration.downgrade)
    assert 'uuid' not in _run(migration.downgrade)
    assert 'uuid' in _run(migration.upgrade)
    assert 'uuid' in _run(migration.upgrade)

    with db.engine.connect() as conn:
        value = conn.execute(sa.text('SELECT uuid FROM extension_request WHERE id = :i'),
                             {'i': er_id}).scalar()
        assert value is not None
        indexes = {i['name'] for i in sa.inspect(conn).get_indexes('extension_request')}
    assert 'ix_extension_request_uuid' in indexes

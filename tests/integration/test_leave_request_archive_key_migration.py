"""Migration u6p7q8r9s0t1: archive_key 'leave_request' on the leave-request archive (data only)."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app import db
from app.models.archive import Archive
from app.models.phase import Phase
from app.models.step import Step

MIGRATION = (Path(__file__).resolve().parents[2] / 'migrations' / 'versions'
             / 'u6p7q8r9s0t1_leave_request_archive_key.py')


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location('mig_u6p7', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _step(phase_name, name='Permanencia'):
    phase = Phase.query.filter_by(name=phase_name).first()
    if phase is None:
        phase = Phase(name=phase_name, description=phase_name)
        db.session.add(phase)
        db.session.flush()
    step = Step(name=name, description=name, phase_id=phase.id)
    db.session.add(step)
    db.session.flush()
    return step


def _archive(step, name, key=None, active=True):
    archive = Archive(name=name, description=name, file_path=None, step_id=step.id)
    archive.archive_key = key
    archive.is_active = active
    db.session.add(archive)
    db.session.flush()
    return archive


def _backfill(migration):
    result = migration.backfill_leave_request_key(db.session.connection())
    db.session.commit()
    db.session.expire_all()
    return result


def test_revision_chain(migration):
    assert migration.revision == 'u6p7q8r9s0t1'
    assert migration.down_revision == 't5o6p7q8r9s0'


def test_keys_the_leave_archive_idempotently(app, migration):
    step = _step('permanence')
    other = _archive(step, 'Constancia de calificaciones')
    leave = _archive(step, 'Solicitud de Baja Temporal')
    db.session.commit()

    assert _backfill(migration) == leave.id
    assert leave.archive_key == 'leave_request'
    assert other.archive_key is None
    # Second run: already keyed, nothing changes.
    assert _backfill(migration) is None
    assert Archive.query.filter_by(archive_key='leave_request').count() == 1


def test_already_keyed_archive_is_left_alone(app, migration):
    step = _step('permanence')
    keyed = _archive(step, 'Baja temporal (formato nuevo)', key='leave_request')
    legacy = _archive(step, 'Solicitud de Baja Temporal')
    db.session.commit()

    assert _backfill(migration) is None
    assert keyed.archive_key == 'leave_request' and legacy.archive_key is None


def test_exact_name_wins_among_several_candidates(app, migration):
    step = _step('permanence')
    _archive(step, 'Formato de baja temporal')
    leave = _archive(step, 'Solicitud de Baja Temporal')
    db.session.commit()

    assert _backfill(migration) == leave.id


def test_ambiguous_inactive_or_other_phase_is_a_noop(app, migration, capsys):
    permanence = _step('permanence')
    _archive(permanence, 'Solicitud de Baja Temporal', active=False)
    _archive(_step('admission', 'Documentos'), 'Solicitud de Baja Temporal')
    _archive(permanence, 'Formato de baja temporal A')
    _archive(permanence, 'Formato de baja temporal B')
    db.session.commit()

    assert _backfill(migration) is None
    assert Archive.query.filter_by(archive_key='leave_request').count() == 0
    assert 'NOTICE' in capsys.readouterr().out


def test_upgrade_and_downgrade_through_alembic(app, migration):
    leave_id = _archive(_step('permanence'), 'Solicitud de Baja Temporal').id
    db.session.commit()
    db.session.remove()

    for step in (migration.upgrade, migration.upgrade, migration.downgrade):
        with db.engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                step()

    assert db.session.get(Archive, leave_id).archive_key == 'leave_request'

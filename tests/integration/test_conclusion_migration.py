"""Data part of migration q2l3m4n5o6p7 (conclusion archive keys and flags)."""

import importlib.util
from pathlib import Path

import pytest

from app import db
from app.models.archive import Archive
from app.models.phase import Phase
from app.models.step import Step

MIGRATION = (Path(__file__).resolve().parents[2] / 'migrations' / 'versions'
             / 'q2l3m4n5o6p7_conclusion.py')


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location('mig_q2l3', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _step(phase_name, name):
    phase = Phase.query.filter_by(name=phase_name).first()
    if phase is None:
        phase = Phase(name=phase_name, description=phase_name)
        db.session.add(phase)
        db.session.flush()
    step = Step(name=name, description=name, phase_id=phase.id)
    db.session.add(step)
    db.session.flush()
    return step


def _archive(step, name, description=None):
    archive = Archive(name=name, description=description or name, file_path=None,
                      step_id=step.id)
    db.session.add(archive)
    db.session.flush()
    return archive


def test_backfill_keys_flags_and_description_idempotently(app, migration):
    ms = _step('admission', 'Requisitos de Maestrías')
    phd = _step('admission', 'Documentos Específicos DCI')
    general = _step('conclusion', 'Requisitos Generales')
    ms_conclusion = _step('conclusion', 'Requisitos de Maestrías')

    title_ms = _archive(ms, 'Título')
    english_ms = _archive(ms, 'Comprobante Inglés')
    title_phd = _archive(phd, 'Título')
    english_phd = _archive(phd, 'Comprobante de Inglés')
    prev = _archive(general, 'Título del Grado Anterior')
    originality = _archive(general, 'Carta de Originalidad',
                           'Carta de Originalidad con Similitud >30%.')
    user_letter = _archive(ms_conclusion, 'Carta de Usuario')
    # Two archives match: ambiguous, so it is skipped.
    _archive(general, 'No Adeudos')
    _archive(general, 'No Adeudos')
    # Already keyed: left alone.
    keyed = _archive(general, 'Documento de Tesis Final')
    keyed.archive_key = 'custom_key'
    db.session.commit()

    counts = migration.backfill_conclusion_archives(db.session.connection())
    db.session.commit()
    db.session.expire_all()

    assert title_ms.archive_key == 'admission_degree_title_ms'
    assert english_ms.archive_key == 'admission_english_ms'
    assert title_phd.archive_key == 'admission_degree_title_phd'
    assert english_phd.archive_key == 'admission_english_phd'
    assert prev.archive_key == 'conclusion_previous_degree'
    assert user_letter.archive_key == 'conclusion_user_letter'
    assert originality.archive_key == 'conclusion_originality_letter'
    assert keyed.archive_key == 'custom_key'
    assert Archive.query.filter_by(name='No Adeudos', archive_key=None).count() == 2
    assert originality.issued_by_institution and originality.allow_coordinator_upload
    assert not prev.issued_by_institution
    assert originality.description == 'Carta de Originalidad con Similitud <30%.'
    assert counts == {'archive_key': 7, 'issued_by_institution': 1, 'description': 1}

    again = migration.backfill_conclusion_archives(db.session.connection())
    assert again == {'archive_key': 0, 'issued_by_institution': 0, 'description': 0}

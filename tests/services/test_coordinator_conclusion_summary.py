"""Coordinator dashboard: real conclusion progress + condition requirement options."""

from app import db
from app.models import Archive, Phase, Step
from app.services import coordinator_service, deliberation_service
from tests.support.factories import enroll, make_program, make_user


def _set_status(up, status):
    type(up).query.filter_by(id=up.id).update({'academic_status': status})
    db.session.expire(up)


def _enrolled(status='active'):
    program = make_program(make_user('program_admin'))
    up = enroll(make_user('student'), program, 'enrolled')
    _set_status(up, status)
    db.session.commit()
    return up


def test_summary_not_started_is_pending(app):
    up = _enrolled()
    assert coordinator_service.conclusion_summary(up) == {
        'conclusion_stage': 'Inicial', 'conclusion_progress': 0, 'conclusion_status': 'pending'}


def test_summary_titled_is_completed(app):
    up = _enrolled('titled')
    assert coordinator_service.conclusion_summary(up) == {
        'conclusion_stage': 'Titulado', 'conclusion_progress': 100,
        'conclusion_status': 'completed'}


def test_summary_graduated_is_in_progress(app):
    up = _enrolled('graduated')
    summary = coordinator_service.conclusion_summary(up)
    assert summary['conclusion_status'] == 'in_progress'
    assert 0 < summary['conclusion_progress'] < 100


def test_summary_skips_queries_when_not_included(app):
    up = _enrolled('titled')
    assert coordinator_service.conclusion_summary(up, include=False)['conclusion_progress'] == 0


def test_list_conclusion_requirements_only_conclusion_keys(app):
    phase = Phase(name='conclusion', description='c')
    db.session.add(phase)
    db.session.flush()
    step = Step(name='s', description='s', phase_id=phase.id)
    db.session.add(step)
    db.session.flush()
    for name, key in (('Título previo', 'conclusion_previous_degree'),
                      ('Otro', 'admission_english_ms'), ('Sin clave', None)):
        a = Archive(name=name, description=name, file_path=None, step_id=step.id)
        a.archive_key = key
        db.session.add(a)
    db.session.commit()
    assert deliberation_service.list_conclusion_requirements() == [
        {'key': 'conclusion_previous_degree', 'name': 'Título previo'}]


def test_summary_relevance_is_status_or_thesis_not_phase(app):
    from app.services import conclusion_service

    up = _enrolled('active')
    assert not coordinator_service.conclusion_relevant(up)
    conclusion_service.register_thesis(up.program.coordinator, up.id, 'Tesis temprana')
    assert coordinator_service.conclusion_relevant(up)
    assert coordinator_service.conclusion_summary(up) == {
        'conclusion_stage': 'Tesis registrada', 'conclusion_progress': 15,
        'conclusion_status': 'in_progress'}
    assert coordinator_service.conclusion_relevant(_enrolled('graduated'))
    assert coordinator_service.conclusion_relevant(_enrolled('titled'))

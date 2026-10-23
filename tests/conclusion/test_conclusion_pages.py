"""Phase 6C: student "Mi conclusión" page, requirement uploads and "Mis tesistas"."""

import io

import pytest

from app import db
from app.models import Archive, Phase, ProgramStep, Step, Submission
from app.models.user_program import UserProgram
from app.services import conclusion_service as svc
from tests.support.factories import enroll, grant, make_program, make_user

HX = {'HX-Request': 'true'}


def _step(program, name='Requisitos Generales'):
    phase = Phase.query.filter_by(name='conclusion').first()
    if phase is None:
        phase = Phase(name='conclusion', description='conclusion')
        db.session.add(phase)
        db.session.flush()
    step = Step(name=name, description=name, phase_id=phase.id)
    db.session.add(step)
    db.session.flush()
    db.session.add(ProgramStep(sequence=1, program_id=program.id, step_id=step.id))
    db.session.flush()
    return step


def _archive(step, name, key, institution=False):
    archive = Archive(name=name, description=name, file_path=None, step_id=step.id)
    archive.archive_key = key
    archive.issued_by_institution = institution
    archive.allow_coordinator_upload = institution
    db.session.add(archive)
    db.session.flush()
    return archive


def _status(up, status):
    UserProgram.query.filter_by(id=up.id).update({'academic_status': status})
    db.session.expire(up)


def _pdf(name='doc.pdf'):
    return (io.BytesIO(b'%PDF-1.4 test'), name)


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    program = make_program(coord)
    step = _step(program)
    thesis_doc = _archive(step, 'Documento de Tesis Final', 'conclusion_thesis_document')
    originality = _archive(step, 'Carta de Originalidad', 'conclusion_originality_letter',
                           institution=True)
    student = make_user('student')
    up = enroll(student, program, 'enrolled')
    _status(up, 'active')
    teacher = make_user('teacher')
    grant(student.role, 'conclusion.page.view_own')
    grant(teacher.role, 'conclusion.page.my_theses')
    outsider = make_user('program_admin')
    db.session.commit()
    return {'coord': coord, 'program': program, 'student': student, 'up': up,
            'teacher': teacher, 'outsider': outsider,
            'thesis_doc': thesis_doc, 'originality': originality}


def test_student_sees_own_page(world, login):
    svc.register_thesis(world['coord'], world['up'].id, 'Optimización de inventarios')
    res = login(world['student']).get('/conclusion/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Mi conclusión' in html
    assert 'Optimización de inventarios' in html
    assert 'Documento de Tesis Final' in html
    assert 'Los requisitos se abren al egreso' in html
    assert 'Lo carga la coordinación' in html


def test_other_roles_denied(world, login):
    denied = (302, 403)  # page routes redirect a refused user
    assert login(world['outsider']).get('/conclusion/').status_code in denied
    assert login(world['teacher']).get('/conclusion/').status_code in denied
    assert login(world['student']).get('/conclusion/theses').status_code in denied


def test_foreign_program_selector_is_404(world, login):
    other = make_program(make_user('program_admin'))
    db.session.commit()
    res = login(world['student']).get(f'/conclusion/?program={other.id}')
    assert res.status_code == 404


def test_upload_happy_path(world, login):
    _status(world['up'], 'graduated')
    client = login(world['student'])
    page = client.get('/conclusion/').get_data(as_text=True)
    assert 'type="file"' in page
    res = client.post(
        f"/conclusion/requirements/{world['thesis_doc'].uuid}",
        data={'program': world['program'].id, 'file': _pdf()},
        content_type='multipart/form-data', headers=HX)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'En revisión' in html
    assert 'siiap:flash' in res.headers.get('HX-Trigger', '')
    sub = Submission.query.filter_by(archive_id=world['thesis_doc'].id).one()
    assert sub.status == 'pending'
    assert sub.user_program_id == world['up'].id


def test_upload_refused_for_institution_archive(world, login):
    _status(world['up'], 'graduated')
    res = login(world['student']).post(
        f"/conclusion/requirements/{world['originality'].uuid}",
        data={'program': world['program'].id, 'file': _pdf()},
        content_type='multipart/form-data', headers=HX)
    assert res.status_code == 400
    assert Submission.query.filter_by(archive_id=world['originality'].id).count() == 0


def test_upload_refused_before_graduation(world, login):
    res = login(world['student']).post(
        f"/conclusion/requirements/{world['thesis_doc'].uuid}",
        data={'program': world['program'].id, 'file': _pdf()},
        content_type='multipart/form-data', headers=HX)
    assert res.status_code == 400
    assert Submission.query.filter_by(archive_id=world['thesis_doc'].id).count() == 0


def test_my_theses_lists_only_own(world, login):
    svc.register_thesis(world['coord'], world['up'].id, 'Tesis de mi tesista')
    svc.add_member(world['coord'], world['up'].id, 'tutorial', 'director', user_id=world['teacher'].id)
    other_student = make_user('student')
    other_up = enroll(other_student, world['program'], 'enrolled')
    _status(other_up, 'active')
    svc.register_thesis(world['coord'], other_up.id, 'Tesis ajena')
    db.session.commit()

    res = login(world['teacher']).get('/conclusion/theses')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Tesis de mi tesista' in html
    assert 'director(a)' in html
    assert 'Tesis ajena' not in html


def test_upload_without_htmx_redirects_to_the_page(world, login):
    _status(world['up'], 'graduated')
    res = login(world['student']).post(
        f"/conclusion/requirements/{world['thesis_doc'].uuid}",
        data={'program': world['program'].id, 'file': _pdf()},
        content_type='multipart/form-data')
    assert res.status_code == 302
    assert res.headers['Location'].endswith(f"/conclusion/?program={world['program'].id}")
    assert Submission.query.filter_by(archive_id=world['thesis_doc'].id).one().status == 'pending'

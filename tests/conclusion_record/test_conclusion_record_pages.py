"""Phase 6C: the coordinator's Conclusión tab of the student record."""

import io
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from flask import g

from app import db
from app.models import Archive, Phase, ProgramStep, Step, Submission
from app.models.admission_condition import AdmissionCondition
from app.models.grade_exam import GradeExam
from app.models.thesis import Thesis
from app.models.user_program import UserProgram
from app.services import conclusion_service as svc
from tests.support.factories import enroll, grant, make_program, make_user

HX = {'HX-Request': 'true'}
VIEW = ('students.page.view_record', 'students.api.view_record')


def _step(program):
    phase = Phase.query.filter_by(name='conclusion').first()
    if phase is None:
        phase = Phase(name='conclusion', description='conclusion')
        db.session.add(phase)
        db.session.flush()
    step = Step(name='Requisitos', description='r', phase_id=phase.id)
    db.session.add(step)
    db.session.flush()
    db.session.add(ProgramStep(sequence=1, program_id=program.id, step_id=step.id))
    db.session.flush()
    return step


def _archive(step, name, key, institution=False):
    a = Archive(name=name, description=name, file_path=None, step_id=step.id)
    a.archive_key = key
    a.issued_by_institution = institution
    a.allow_coordinator_upload = institution
    db.session.add(a)
    db.session.flush()
    return a


def _status(up, status):
    UserProgram.query.filter_by(id=up.id).update({'academic_status': status})
    db.session.expire(up)


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    other = make_user('program_admin')
    postgrad = make_user('postgraduate_admin')
    program = make_program(coord)
    make_program(other)
    student = make_user('student')
    up = enroll(student, program, 'enrolled')
    _status(up, 'active')
    step = _step(program)
    doc = _archive(step, 'Documento de Tesis', 'conclusion_thesis_document')
    cert = _archive(step, 'Carta de Originalidad', 'conclusion_originality_letter', True)
    for role in (coord.role, other.role):
        grant(role, *VIEW, 'conclusion.page.manage')
    grant(postgrad.role, 'academic_periods.api.create', *VIEW, 'conclusion.page.manage', 'conclusion.page.revert_titled')
    db.session.commit()
    return SimpleNamespace(coord=coord, other=other, postgrad=postgrad, student=student,
                           up=up, program=program, doc=doc, cert=cert)


def _base(w):
    return f'/students/{w.student.uuid}/record/conclusion'


def _ready(w):
    svc.register_thesis(w.coord, w.up.id, 'Tesis lista')
    for role in ('president', 'secretary', 'vocal'):
        svc.add_member(w.coord, w.up.id, 'exam', role, external_name=f'Dr {role}')
    _status(w.up, 'graduated')
    for archive in (w.doc, w.cert):
        ps = ProgramStep.query.filter_by(program_id=w.program.id, step_id=archive.step_id).first()
        db.session.add(Submission(file_path=f'{w.student.id}/x/{archive.id}.pdf', status='approved',
                                  user_id=w.student.id, archive_id=archive.id,
                                  program_step_id=ps.id, semester=None,
                                  user_program_id=w.up.id))
    db.session.commit()


# ─── Access ──────────────────────────────────────────────────────────────────

def test_student_is_denied(world, login):
    assert login(world.student).get(_base(world), headers=HX).status_code == 403


def test_out_of_scope_is_404(world, login):
    assert login(world.other).get(_base(world), headers=HX).status_code == 404
    res = login(world.other).post(_base(world) + '/thesis', headers=HX, data={'title': 'x'})
    assert res.status_code == 404


def test_without_conclusion_permission_is_403(world, login):
    teacher = make_user('teacher')
    grant(teacher.role, *VIEW)
    assert login(teacher).get(_base(world), headers=HX).status_code == 403


def test_non_htmx_redirects_to_tab(world, login):
    res = login(world.coord).get(_base(world))
    assert res.status_code == 302
    assert res.headers['Location'].endswith('/record?tab=conclusion')


# ─── Fragment ────────────────────────────────────────────────────────────────

def test_fragment_renders_sections(world, login):
    res = login(world.coord).get(_base(world), headers=HX)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    for marker in ('conclusionThesisForm', 'Comité tutorial', 'Sínodo', 'conclusionConditionForm',
                   'Documento de Tesis', 'conclusionBlockers'):
        assert marker in html
    assert 'conclusionRevertForm' not in html
    assert 'HX-Request' in res.headers.get('Vary', '')


# ─── Thesis and members ──────────────────────────────────────────────────────

def test_thesis_register_then_update(world, login):
    c = login(world.coord)
    res = c.post(_base(world) + '/thesis', headers=HX,
                 data={'title': 'Mi tesis', 'research_line': 'Logística', 'registered_at': '2026-03-01'})
    assert res.status_code == 200
    assert 'Mi tesis' in res.get_data(as_text=True)
    assert Thesis.query.filter_by(user_program_id=world.up.id).one().registered_at == date(2026, 3, 1)
    res = c.post(_base(world) + '/thesis', headers=HX, data={'title': 'Otra tesis'})
    assert res.status_code == 200
    db.session.expire_all()
    assert Thesis.query.filter_by(user_program_id=world.up.id).one().title == 'Otra tesis'


def test_thesis_bad_date(world, login):
    res = login(world.coord).post(_base(world) + '/thesis', headers=HX,
                                  data={'title': 'T', 'registered_at': 'nope'})
    assert res.status_code == 400
    assert Thesis.query.count() == 0


def test_member_add_and_remove(world, login):
    svc.register_thesis(world.coord, world.up.id, 'T')
    teacher = make_user('teacher', first_name='Elena', last_name='Torres')
    db.session.commit()
    c = login(world.coord)
    res = c.post(_base(world) + '/members', headers=HX,
                 data={'body': 'tutorial', 'role': 'director', 'person': 'internal',
                       'user_id': teacher.id})
    assert res.status_code == 200 and 'Elena' in res.get_data(as_text=True)
    res = c.post(_base(world) + '/members', headers=HX,
                 data={'body': 'exam', 'role': 'vocal', 'person': 'external',
                       'external_name': 'Dra. Externa', 'external_institution': 'UACJ'})
    assert 'Dra. Externa' in res.get_data(as_text=True)
    member = svc.get_thesis(world.up).members_of('tutorial')[0]
    res = c.post(f'{_base(world)}/members/{member.id}/remove', headers=HX, data={})
    assert res.status_code == 200
    db.session.expire_all()
    assert svc.get_thesis(world.up).members_of('tutorial') == []


def test_member_add_without_thesis_fails(world, login):
    res = login(world.coord).post(_base(world) + '/members', headers=HX,
                                  data={'body': 'exam', 'role': 'vocal', 'person': 'external',
                                        'external_name': 'X'})
    assert res.status_code in (400, 404, 409)


# ─── Conditions ──────────────────────────────────────────────────────────────

def test_condition_create_met_and_waive(world, login):
    c = login(world.coord)
    res = c.post(_base(world) + '/conditions', headers=HX,
                 data={'description': 'Entregar constancia', 'archive_id': str(world.doc.uuid),
                       'due_date': '2027-01-15'})
    assert res.status_code == 200 and 'Entregar constancia' in res.get_data(as_text=True)
    c.post(_base(world) + '/conditions', headers=HX, data={'description': 'Segunda'})
    first, second = AdmissionCondition.query.order_by(AdmissionCondition.id).all()
    res = c.post(f'{_base(world)}/conditions/{first.uuid}/resolve', headers=HX,
                 data={'resolution': 'met'})
    assert res.status_code == 200
    bad = c.post(f'{_base(world)}/conditions/{second.uuid}/resolve', headers=HX,
                 data={'resolution': 'waived', 'note': ' '})
    assert bad.status_code == 400
    ok = c.post(f'{_base(world)}/conditions/{second.uuid}/resolve', headers=HX,
                data={'resolution': 'waived', 'note': 'Autorizado por el comité'})
    assert ok.status_code == 200
    db.session.expire_all()
    assert {x.status for x in AdmissionCondition.query.all()} == {'met', 'waived'}


def test_condition_bad_date(world, login):
    res = login(world.coord).post(_base(world) + '/conditions', headers=HX,
                                  data={'description': 'X', 'due_date': 'ayer'})
    assert res.status_code == 400


# ─── Requirements ────────────────────────────────────────────────────────────

def test_institution_upload_only_for_issued_documents(world, login):
    html = login(world.coord).get(_base(world), headers=HX).get_data(as_text=True)
    assert f'upload-{world.cert.uuid}' in html
    assert f'upload-{world.doc.uuid}' not in html


def test_institution_upload_ok_and_student_document_refused(world, login):
    _status(world.up, 'graduated')
    db.session.commit()
    c = login(world.coord)
    res = c.post(f'{_base(world)}/requirements/{world.cert.uuid}/upload', headers=HX,
                 data={'file': (io.BytesIO(b'%PDF-1.4 test'), 'carta.pdf')},
                 content_type='multipart/form-data')
    assert res.status_code == 200
    assert 'Emitido' in res.get_data(as_text=True)
    assert Submission.query.filter_by(archive_id=world.cert.id).one().status == 'approved'
    bad = c.post(f'{_base(world)}/requirements/{world.doc.uuid}/upload', headers=HX,
                 data={'file': (io.BytesIO(b'%PDF-1.4 test'), 'x.pdf')},
                 content_type='multipart/form-data')
    assert bad.status_code == 400


# ─── Exam ────────────────────────────────────────────────────────────────────

def test_schedule_blocked_then_ok_then_result_titles(world, login):
    c = login(world.coord)
    when = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%dT%H:%M')
    blocked = c.post(_base(world) + '/exam', headers=HX, data={'scheduled_at': when, 'place': 'Sala 1'})
    assert blocked.status_code == 400

    _ready(world)
    res = c.post(_base(world) + '/exam', headers=HX,
                 data={'scheduled_at': when, 'place': 'Sala 1', 'notes': 'Traer proyector'})
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'conclusionResultForm' in html and 'Sala 1' in html
    exam = GradeExam.query.one()
    exam.scheduled_at = datetime.now() - timedelta(hours=1)  # the exam was held
    db.session.commit()

    bad = c.post(f'{_base(world)}/exam/{exam.uuid}/result', headers=HX, data={'result': 'approved'})
    assert bad.status_code == 400
    ok = c.post(f'{_base(world)}/exam/{exam.uuid}/result', headers=HX,
                data={'result': 'approved', 'verdict': 'unanimous', 'acta_folio': 'F-12',
                      'held_on': date.today().isoformat(), 'honorific_mention': '1'})
    assert ok.status_code == 200
    db.session.expire_all()
    assert db.session.get(UserProgram, world.up.id).academic_status == 'titled'
    page = ok.get_data(as_text=True)
    assert 'Unanimidad' in page
    assert 'conclusionRevertForm' not in page  # the coordinator lacks the permission


def test_bad_datetime(world, login):
    res = login(world.coord).post(_base(world) + '/exam', headers=HX,
                                  data={'scheduled_at': 'x', 'place': 'Sala'})
    assert res.status_code == 400


def test_cancel_exam(world, login):
    _ready(world)
    exam = svc.schedule_exam(world.coord, world.up.id, datetime.now() + timedelta(days=5), 'Sala')
    c = login(world.coord)
    res = c.post(f'{_base(world)}/exam/{exam.uuid}/cancel', headers=HX,
                 data={'reason': 'Cambio de fecha'})
    assert res.status_code == 200
    db.session.expire_all()
    assert db.session.get(GradeExam, exam.id).status == 'cancelled'
    again = c.post(f'{_base(world)}/exam/{exam.uuid}/cancel', headers=HX, data={})
    assert again.status_code in (400, 409)


# ─── Revert titled ───────────────────────────────────────────────────────────

def test_revert_titled(world, login):
    _ready(world)
    exam = svc.schedule_exam(world.coord, world.up.id, datetime.now() + timedelta(days=3), 'Sala')
    exam.scheduled_at = datetime.now() - timedelta(days=1)
    db.session.commit()
    svc.record_exam_result(world.coord, world.up.id, exam.uuid, 'approved', verdict='majority',
                           acta_folio='F-1', held_on=date.today())
    assert login(world.coord).post(_base(world) + '/revert-titled', headers=HX,
                                   data={'reason': 'x'}).status_code == 403
    g.pop('_login_user', None)  # the test app context caches the logged-in user
    html = login(world.postgrad).get(_base(world), headers=HX).get_data(as_text=True)
    assert 'conclusionRevertForm' in html
    pg = login(world.postgrad)
    assert pg.post(_base(world) + '/revert-titled', headers=HX, data={'reason': ' '}).status_code == 400
    ok = pg.post(_base(world) + '/revert-titled', headers=HX, data={'reason': 'Acta capturada por error'})
    assert ok.status_code == 200
    db.session.expire_all()
    assert db.session.get(UserProgram, world.up.id).academic_status == 'graduated'


# ─── Children bound to the URL's student program ─────────────────────────────

def _classmate(w):
    other = make_user('student')
    up = enroll(other, w.program, 'enrolled')
    _status(up, 'active')
    db.session.commit()
    return up


def test_condition_of_another_student_is_404_through_this_url(world, login):
    other_up = _classmate(world)
    cond = svc.create_condition(world.coord, other_up.id, 'Ajena')
    res = login(world.coord).post(f'{_base(world)}/conditions/{cond.uuid}/resolve', headers=HX,
                                  data={'resolution': 'met'})
    assert res.status_code == 404
    db.session.expire_all()
    assert db.session.get(AdmissionCondition, cond.id).status == 'pending'


def test_exam_of_another_student_is_404_through_this_url(world, login):
    _ready(world)
    exam = svc.schedule_exam(world.coord, world.up.id, datetime.now() + timedelta(days=5), 'Sala')
    other_up = _classmate(world)
    other_base = f'/students/{other_up.user.uuid}/record/conclusion'
    c = login(world.coord)
    assert c.post(f'{other_base}/exam/{exam.uuid}/cancel', headers=HX,
                  data={}).status_code == 404
    assert c.post(f'{other_base}/exam/{exam.uuid}/result', headers=HX,
                  data={'result': 'suspended'}).status_code == 404
    db.session.expire_all()
    assert db.session.get(GradeExam, exam.id).status == 'scheduled'

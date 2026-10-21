"""Phase 6B2, Task 4: admin corrections, capture extension and period capture dates."""

import json
from datetime import timedelta

import pytest
from flask import g

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.course_group import CourseGroup
from app.models.curriculum_plan import CurriculumPlan
from app.models.grade_correction import GradeCorrection
from app.models.subject import Subject
from app.schemas.curriculum import CourseGroupIn
from app.services import academic_period_service as period_svc
from app.services import course_group_service as group_svc
from app.services import grading_service
from app.utils.datetime_utils import now_local
from tests.support.factories import (
    enroll, grant, make_academic_period, make_program, make_user,
)

HX = {'HX-Request': 'true'}
DECIDE = 'grades.page.decide_correction'
EXTEND = 'grades.page.extend_capture'


def _switch(login, user):
    if hasattr(g, '_login_user'):
        del g._login_user
    return login(user)


def _flash(res):
    return json.loads(res.headers['HX-Trigger'])['siiap:flash']


@pytest.fixture
def world(app):
    admin = make_user('postgraduate_admin')
    coord = make_user('program_admin')
    teacher = make_user('teacher')
    program = make_program(coord)
    period = make_academic_period()
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    subject = Subject(plan_id=plan.id, key='M1', name='Matemáticas', credits=5,
                      suggested_semester=1, kind='required', sequence=1)
    db.session.add(subject)
    db.session.flush()
    grant(admin.role, DECIDE, EXTEND, 'course_groups.page.manage',
          'academic_periods.api.create')  # global program scope
    grant(coord.role, 'course_groups.page.manage')
    student = make_user('student', first_name='Ana', last_name='Alumno')
    up = enroll(student, program, 'enrolled')
    up.academic_status = 'active'
    up.curriculum_plan_id = plan.id
    up.current_semester = 1
    group = group_svc.save_group(
        program.id, CourseGroupIn(subject_id=subject.id, academic_period_id=period.id,
                                  group_code='A', capacity=5, teacher_id=teacher.id),
        coord.id)
    enrollment = CourseEnrollment(
        user_program_id=up.id, subject_id=subject.id, academic_period_id=period.id,
        course_group_id=group.id, attempt=1, attempt_type='ordinary', status='graded',
        grade=60, result='failed')
    db.session.add(enrollment)
    db.session.flush()
    correction = grading_service.request_correction(enrollment.id, '85', 'Error de captura',
                                                    teacher.id)
    return {'admin': admin, 'coord': coord, 'teacher': teacher, 'group': group,
            'enrollment': enrollment, 'correction': correction, 'period': period, 'up': up}


# -- corrections list and decision --------------------------------------------

def test_admin_lists_pending(world, login):
    res = login(world['admin']).get('/grade-corrections/')
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert 'Matemáticas' in html and 'Error de captura' in html and 'Ana' in html
    assert 'id="gradeCorrectionsList"' in html


def test_non_admin_is_403(world, login):
    assert login(world['coord']).get('/grade-corrections/', headers=HX).status_code == 403
    assert _switch(login, world['teacher']).post(
        f"/grade-corrections/{world['correction'].id}/decide",
        data={'decision': 'approve'}, headers=HX).status_code == 403


def test_approve_changes_grade(world, login):
    res = login(world['admin']).post(f"/grade-corrections/{world['correction'].id}/decide",
                                     data={'decision': 'approve'}, headers=HX)
    assert res.status_code == 200
    assert _flash(res)['level'] == 'success'
    assert 'Sin solicitudes pendientes' in res.get_data(as_text=True)
    db.session.expire_all()
    e = db.session.get(CourseEnrollment, world['enrollment'].id)
    assert (e.grade, e.result) == (85, 'passed')


def test_reject_requires_notes(world, login):
    client = login(world['admin'])
    url = f"/grade-corrections/{world['correction'].id}/decide"
    assert client.post(url, data={'decision': 'reject', 'notes': ' '},
                       headers=HX).status_code == 400
    res = client.post(url, data={'decision': 'reject', 'notes': 'No procede'}, headers=HX)
    assert res.status_code == 200
    db.session.expire_all()
    assert db.session.get(CourseEnrollment, world['enrollment'].id).grade == 60
    assert db.session.get(GradeCorrection, world['correction'].id).status == 'rejected'


def test_invalid_decision_is_400(world, login):
    res = login(world['admin']).post(f"/grade-corrections/{world['correction'].id}/decide",
                                     data={'decision': 'maybe'}, headers=HX)
    assert res.status_code == 400


def test_withdrawal_warning(world, login):
    e = world['enrollment']
    e.attempt_type = 'special'
    world['up'].academic_status = 'withdrawn'
    db.session.flush()
    res = login(world['admin']).post(f"/grade-corrections/{world['correction'].id}/decide",
                                     data={'decision': 'approve'}, headers=HX)
    flash = _flash(res)
    assert flash['level'] == 'warning'
    assert 'baja definitiva' in flash['message']


# -- capture extension ----------------------------------------------------------

def test_group_detail_shows_acta(world, login):
    res = login(world['coord']).get(f"/course-groups/{world['group'].uuid}", headers=HX)
    html = res.get_data(as_text=True)
    assert 'Acta abierta' in html and 'Reprobada' in html
    assert 'Ampliar captura' not in html  # coordinator lacks the permission


def test_extend_capture(world, login):
    client = login(world['admin'])
    until = (now_local().date() + timedelta(days=5)).isoformat()
    url = f"/course-groups/{world['group'].uuid}/extend-capture"
    res = client.post(url, data={'until': until, 'reason': 'Retraso'}, headers=HX)
    assert res.status_code == 200 and _flash(res)['message'] == 'Captura ampliada.'
    assert 'Ampliar captura hasta' in res.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(CourseGroup, world['group'].id).capture_until.isoformat() == until


def test_extend_capture_permission_and_past_date(world, login):
    url = f"/course-groups/{world['group'].uuid}/extend-capture"
    until = (now_local().date() + timedelta(days=5)).isoformat()
    assert login(world['coord']).post(url, data={'until': until, 'reason': 'x'},
                                      headers=HX).status_code == 403
    client = _switch(login, world['admin'])
    past = (now_local().date() - timedelta(days=1)).isoformat()
    assert client.post(url, data={'until': past, 'reason': 'x'}, headers=HX).status_code == 400
    assert client.post(url, data={'until': 'nope', 'reason': 'x'}, headers=HX).status_code == 400


# -- academic periods -------------------------------------------------------------

def _period_data(**over):
    base = dict(code='20991', name='Periodo futuro', start_date='2099-02-01',
                end_date='2099-06-01', admission_start_date='2098-10-01',
                admission_end_date='2099-01-15')
    base.update(over)
    return base


def test_period_create_with_capture_dates(app):
    p = period_svc.create_academic_period(
        _period_data(grade_capture_start='2099-05-20', grade_capture_end='2099-06-10'))
    assert p.grade_capture_start.isoformat() == '2099-05-20'
    assert p.to_dict()['grade_capture_end'] == '2099-06-10'


def test_period_create_without_capture_dates(app):
    p = period_svc.create_academic_period(_period_data(grade_capture_start='',
                                                       grade_capture_end=None))
    assert p.grade_capture_start is None and p.grade_capture_end is None


def test_period_capture_start_after_end_fails(app):
    with pytest.raises(period_svc.InvalidDateRange):
        period_svc.create_academic_period(
            _period_data(grade_capture_start='2099-06-10', grade_capture_end='2099-05-20'))


def test_period_update_capture_dates(app):
    p = period_svc.create_academic_period(_period_data())
    period_svc.update_academic_period(p.id, {'grade_capture_start': '2099-05-01'})
    assert p.grade_capture_start.isoformat() == '2099-05-01'
    with pytest.raises(period_svc.InvalidDateRange):
        period_svc.update_academic_period(p.id, {'grade_capture_end': '2099-04-01'})
    db.session.rollback()


def test_period_api_roundtrip(app, login):
    admin = make_user('postgraduate_admin')
    grant(admin.role, 'academic_periods.api.create', 'academic_periods.api.update')
    client = login(admin)
    res = client.post('/api/v1/academic-periods', json=_period_data(
        grade_capture_start='2099-05-20', grade_capture_end='2099-06-10'))
    assert res.status_code == 201
    pid = res.get_json()['data']['id']
    assert res.get_json()['data']['grade_capture_start'] == '2099-05-20'
    bad = client.patch(f'/api/v1/academic-periods/{pid}',
                       json={'grade_capture_start': '2099-07-01'})
    assert bad.status_code == 400

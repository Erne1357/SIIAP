"""Phase 6B2 Task 3: acta capture and closing from Docencia -> Mis grupos."""

import json
from datetime import timedelta

import pytest

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.curriculum_plan import CurriculumPlan
from app.models.grade_correction import GradeCorrection
from app.models.subject import Subject
from app.models.user_program import UserProgram
from app.schemas.curriculum import CourseGroupIn
from app.services import course_enrollment_service as enroll_svc
from app.services import course_group_service as group_svc
from app.services import grading_service as grading
from app.utils.datetime_utils import now_local
from tests.support.factories import (
    enroll, grant, make_academic_period, make_program, make_user,
)

HX = {'HX-Request': 'true'}


def _flash(res) -> dict:
    return json.loads(res.headers['HX-Trigger'])['siiap:flash']


def _student(w, first, last, control):
    user = make_user('student', first_name=first, last_name=last, control_number=control)
    up = enroll(user, w['program'], admission_status='enrolled')
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': 'active', 'curriculum_plan_id': w['plan'].id,
         'current_semester': 1})
    db.session.expire(up)
    return up


def _group(w, subject, period=None, code='A', teacher=None):
    return group_svc.save_group(w['program'].id, CourseGroupIn(
        subject_id=subject.id, academic_period_id=(period or w['period']).id,
        group_code=code, capacity=10, teacher_id=(teacher or w['teacher']).id),
        w['coord'].id)


@pytest.fixture
def w(app):
    coord = make_user('program_admin')
    other_coord = make_user('program_admin')
    program = make_program(coord)
    make_program(other_coord)
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    math = Subject(plan_id=plan.id, name='Matemáticas', key='MAT', credits=5,
                   suggested_semester=1, kind='required', sequence=0)
    db.session.add(math)
    db.session.flush()
    teacher = make_user('teacher')
    other_teacher = make_user('teacher')
    for role in (teacher.role, coord.role, other_coord.role):
        grant(role, 'teaching.page.my_groups', 'grades.page.capture',
              'grades.page.request_correction')
    w = {'coord': coord, 'other_coord': other_coord, 'program': program, 'plan': plan,
         'math': math, 'period': make_academic_period(), 'teacher': teacher,
         'other_teacher': other_teacher}
    w['group'] = _group(w, math)
    w['up1'] = _student(w, 'Ana', 'Zapata', 'C-001')
    w['up2'] = _student(w, 'Beto', 'Yáñez', 'C-002')
    w['e1'] = enroll_svc.enroll(w['group'].id, w['up1'].id, coord.id)
    w['e2'] = enroll_svc.enroll(w['group'].id, w['up2'].id, coord.id)
    w['url'] = f"/teaching/groups/{w['group'].uuid}"
    return w


def _closed(w):
    """Capture and close the acta through the service (85 / 50)."""
    grading.save_draft(w['group'].id, {w['e1'].id: '85', w['e2'].id: '50'}, w['teacher'].id)
    grading.close_acta(w['group'].id, w['teacher'].id)


def test_teacher_sees_inputs(w, login):
    html = login(w['teacher']).get(w['url']).get_data(as_text=True)
    assert 'id="actaRoot"' in html
    assert f"name=\"grade-{w['e1'].id}\"" in html
    assert 'Guardar borrador' in html and 'Cerrar acta' in html
    assert 'data-confirm-title="Cerrar acta"' in html


def test_save_draft(w, login):
    res = login(w['teacher']).post(
        f"{w['url']}/grades", headers=HX,
        data={f"grade-{w['e1'].id}": '85', f"grade-{w['e2'].id}": 'np'})
    assert res.status_code == 200
    assert _flash(res)['message'] == 'Borrador guardado.'
    e1, e2 = (db.session.get(CourseEnrollment, w[k].id) for k in ('e1', 'e2'))
    assert (e1.grade, e1.status) == (85, 'enrolled')
    assert e2.grade_mark == 'NP'
    assert 'value="85"' in res.get_data(as_text=True)


def test_invalid_value_is_400_in_spanish(w, login):
    res = login(w['teacher']).post(
        f"{w['url']}/grades", headers=HX, data={f"grade-{w['e1'].id}": 'abc'})
    assert res.status_code == 400
    assert 'número entero de 0 a 100 o NP' in _flash(res)['message']
    assert db.session.get(CourseEnrollment, w['e1'].id).grade is None


def test_close_requires_all_values(w, login):
    res = login(w['teacher']).post(
        f"{w['url']}/close", headers=HX, data={f"grade-{w['e1'].id}": '85'})
    assert res.status_code == 400
    assert 'Faltan 1 calificaciones' in _flash(res)['message']
    assert w['group'].status == 'open'


def test_close_makes_grades_final(w, login):
    res = login(w['teacher']).post(
        f"{w['url']}/close", headers=HX,
        data={f"grade-{w['e1'].id}": '85', f"grade-{w['e2'].id}": '50'})
    assert res.status_code == 200
    flash = _flash(res)
    assert flash['level'] == 'success' and '2 calificaciones' in flash['message']
    db.session.expire_all()
    assert w['group'].status == 'closed'
    e1, e2 = (db.session.get(CourseEnrollment, w[k].id) for k in ('e1', 'e2'))
    assert (e1.status, e1.result) == ('graded', 'passed')
    assert e2.result == 'failed'
    html = res.get_data(as_text=True)
    assert 'Aprobada' in html and 'Reprobada' in html and 'Acta cerrada' in html
    assert 'name="grade-' not in html
    assert 'Solicitar corrección' in html


def test_failed_special_withdraws_student(w, login):
    up3 = _student(w, 'Carla', 'Xolo', 'C-003')
    periods = [make_academic_period(is_active=False) for _ in range(2)]
    for i, period in enumerate(periods):
        group = _group(w, w['math'], period=period, code=f'P{i}')
        e = enroll_svc.enroll(group.id, up3.id, w['coord'].id)
        grading.save_draft(group.id, {e.id: '40'}, w['teacher'].id)
        grading.close_acta(group.id, w['teacher'].id)
    third = enroll_svc.enroll(w['group'].id, up3.id, w['coord'].id)
    assert third.attempt_type == 'special'
    res = login(w['teacher']).post(
        f"{w['url']}/close", headers=HX,
        data={f"grade-{w['e1'].id}": '90', f"grade-{w['e2'].id}": '90',
              f"grade-{third.id}": 'NP'})
    assert res.status_code == 200
    flash = _flash(res)
    assert flash['level'] == 'warning' and 'Carla' in flash['message']
    up = db.session.get(UserProgram, up3.id)
    db.session.refresh(up)
    assert up.academic_status == 'withdrawn'


def test_another_teacher_gets_404_everywhere(w, login):
    client = login(w['other_teacher'])
    assert client.get(w['url']).status_code == 404
    assert client.post(f"{w['url']}/grades", headers=HX, data={}).status_code == 404
    assert client.post(f"{w['url']}/close", headers=HX, data={}).status_code == 404
    assert client.post(f"{w['url']}/corrections", headers=HX, data={}).status_code == 404


def test_coordinator_in_scope_sees_grades_without_inputs(w, login):
    grading.save_draft(w['group'].id, {w['e1'].id: '85'}, w['teacher'].id)
    client = login(w['coord'])
    html = client.get(w['url']).get_data(as_text=True)
    assert '85' in html and 'name="grade-' not in html
    assert 'Guardar borrador' not in html
    # Not the teacher: the service refuses and the route answers 404.
    assert client.post(f"{w['url']}/grades", headers=HX,
                       data={f"grade-{w['e1'].id}": '90'}).status_code == 404


def test_coordinator_out_of_scope_is_404(w, login):
    assert login(w['other_coord']).get(w['url']).status_code == 404


def test_window_closed_hides_inputs_and_shows_notice(w, login):
    period = w['period']
    tomorrow = now_local().date() + timedelta(days=5)
    period.grade_capture_start = tomorrow
    period.grade_capture_end = tomorrow + timedelta(days=5)
    db.session.commit()
    res = login(w['teacher']).get(w['url'])
    html = res.get_data(as_text=True)
    assert 'name="grade-' not in html
    assert 'La captura de calificaciones no está abierta.' in html
    assert 'Captura del periodo:' in html
    refused = login(w['teacher']).post(
        f"{w['url']}/grades", headers=HX, data={f"grade-{w['e1'].id}": '85'})
    assert refused.status_code == 400


def test_correction_request_and_pending_badge(w, login):
    _closed(w)
    client = login(w['teacher'])
    res = client.post(
        f"{w['url']}/corrections", headers=HX,
        data={'enrollment_id': w['e2'].id, 'new_value': '75', 'reason': 'Error de captura'})
    assert res.status_code == 200
    assert _flash(res)['message'] == 'Solicitud de corrección enviada.'
    pending = GradeCorrection.query.filter_by(
        course_enrollment_id=w['e2'].id, status='pending').one()
    assert pending.new_grade == 75
    html = res.get_data(as_text=True)
    assert 'Corrección pendiente' in html
    assert f"correctionModal-{w['e2'].id}" not in html
    assert f"correctionModal-{w['e1'].id}" in html


def test_second_correction_request_is_400(w, login):
    _closed(w)
    client = login(w['teacher'])
    data = {'enrollment_id': w['e2'].id, 'new_value': '75', 'reason': 'Error'}
    assert client.post(f"{w['url']}/corrections", headers=HX, data=data).status_code == 200
    res = client.post(f"{w['url']}/corrections", headers=HX, data={**data, 'new_value': '80'})
    assert res.status_code == 400
    assert 'pendiente' in _flash(res)['message']
    assert GradeCorrection.query.filter_by(course_enrollment_id=w['e2'].id).count() == 1


def test_correction_requires_reason(w, login):
    _closed(w)
    res = login(w['teacher']).post(
        f"{w['url']}/corrections", headers=HX,
        data={'enrollment_id': w['e2'].id, 'new_value': '75', 'reason': ' '})
    assert res.status_code == 400
    assert 'motivo' in _flash(res)['message']

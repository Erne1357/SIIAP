"""Phase 6B3: correction requests for IMPORTED grades from the record's Kardex tab."""

import pytest

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.curriculum_plan import CurriculumPlan
from app.models.grade_correction import GradeCorrection
from app.models.subject import Subject
from app.models.user_program import UserProgram
from tests.support.factories import (
    enroll, grant, make_academic_period, make_program, make_user,
)

HX = {'HX-Request': 'true'}
VIEW = ('students.page.view_record', 'students.api.view_record')
REQUEST = 'grades.page.request_correction'


def _subject(plan, name, key):
    s = Subject(plan_id=plan.id, name=name, kind='required', key=key, credits=5,
                suggested_semester=1, sequence=0)
    db.session.add(s)
    db.session.flush()
    return s


def _row(up, subject, period, grade, group_id=None):
    row = CourseEnrollment(
        user_program_id=up.id, subject_id=subject.id, academic_period_id=period.id,
        course_group_id=group_id, attempt=1, attempt_type='ordinary',
        status='graded', grade=grade, result='passed')
    db.session.add(row)
    db.session.flush()
    return row


def _student(program, plan, period, subject):
    student = make_user('student')
    up = enroll(student, program, admission_status='enrolled')
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': 'active', 'curriculum_plan_id': plan.id, 'current_semester': 1})
    db.session.expire(up)
    return student, up, _row(up, subject, period, 80)


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    other = make_user('program_admin')
    program = make_program(coord)
    make_program(other)
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    period = make_academic_period()
    math = _subject(plan, 'Matemáticas', 'MAT')
    student, up, imported = _student(program, plan, period, math)
    student2, up2, imported2 = _student(program, plan, period, math)
    grant(coord.role, *VIEW, REQUEST)
    grant(other.role, *VIEW, REQUEST)
    grant(student.role, 'kardex.page.view_own')
    return {'coord': coord, 'other': other, 'student': student, 'up': up,
            'imported': imported, 'imported2': imported2, 'program': program,
            'plan': plan, 'period': period}


def _url(w):
    return f"/students/{w['student'].uuid}/record/kardex/corrections"


def _post(client, w, enrollment_id, value='90', reason='Error de captura'):
    return client.post(_url(w), headers=HX, data={
        'enrollment_id': enrollment_id, 'new_value': value, 'reason': reason,
        'program': w['program'].id})


def test_coordinator_requests_correction(world, login):
    res = _post(login(world['coord']), world, world['imported'].id)
    assert res.status_code == 200
    assert 'siiap:flash' in res.headers['HX-Trigger']
    assert 'Solicitud de corrección enviada al jefe de posgrado.' in res.headers['HX-Trigger'].encode().decode('unicode_escape') \
        or 'enviada' in res.headers['HX-Trigger']
    corr = GradeCorrection.query.filter_by(course_enrollment_id=world['imported'].id).one()
    assert corr.status == 'pending' and corr.new_grade == 90 and corr.old_grade == 80


def test_other_coordinator_is_404(world, login):
    res = _post(login(world['other']), world, world['imported'].id)
    assert res.status_code == 404
    assert GradeCorrection.query.count() == 0


def test_enrollment_of_another_student_is_404(world, login):
    res = _post(login(world['coord']), world, world['imported2'].id)
    assert res.status_code == 404
    assert GradeCorrection.query.count() == 0


def test_malformed_enrollment_is_404(world, login):
    assert _post(login(world['coord']), world, 'abc').status_code == 404


def test_missing_reason_is_rejected(world, login):
    res = _post(login(world['coord']), world, world['imported'].id, reason='  ')
    assert res.status_code == 400
    assert 'motivo' in res.headers['HX-Trigger']
    assert GradeCorrection.query.count() == 0


def test_button_only_in_record_context(world, login):
    html = login(world['coord']).get(
        f"/students/{world['student'].uuid}/record/kardex", headers=HX).get_data(as_text=True)
    assert 'Historial' in html
    assert 'Solicitar corrección' in html
    assert f'data-enrollment-id="{world["imported"].id}"' in html


def test_no_button_without_permission(world, login):
    from app.models.permission import Permission
    from app.models.role_permission import RolePermission
    perm = Permission.query.filter_by(codename=REQUEST).one()
    RolePermission.query.filter_by(
        role_id=world['coord'].role.id, permission_id=perm.id).delete()
    db.session.flush()
    html = login(world['coord']).get(
        f"/students/{world['student'].uuid}/record/kardex", headers=HX).get_data(as_text=True)
    assert 'Historial' in html
    assert 'Solicitar corrección' not in html


def test_group_attempt_has_no_button(world, login):
    from app.models.course_group import CourseGroup
    row = world['imported']
    group = CourseGroup(program_id=world['program'].id, academic_period_id=world['period'].id,
                        subject_id=row.subject_id, group_code='A', capacity=10)
    db.session.add(group)
    db.session.flush()
    row.course_group_id = group.id
    db.session.flush()
    html = login(world['coord']).get(
        f"/students/{world['student'].uuid}/record/kardex", headers=HX).get_data(as_text=True)
    assert 'Historial' not in html
    assert 'data-enrollment-id' not in html


def test_my_kardex_shows_marker_without_button(world, login):
    html = login(world['student']).get('/kardex/').get_data(as_text=True)
    assert 'Historial' in html
    assert 'Solicitar corrección' not in html

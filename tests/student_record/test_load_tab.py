"""Phase 6B1: the record's "Carga" tab (fragment + plan version change)."""

import pytest

from app import db
from app.models.curriculum_plan import CurriculumPlan
from app.models.subject import Subject
from app.models.user_program import UserProgram
from app.schemas.curriculum import CourseGroupIn
from app.services import course_enrollment_service as enroll_svc
from app.services import course_group_service as group_svc
from tests.support.factories import (
    enroll, grant, make_academic_period, make_program, make_user,
)

HX = {'HX-Request': 'true'}
VIEW = ('students.page.view_record', 'students.api.view_record')


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    other = make_user('program_admin')
    viewer = make_user('program_admin')
    program = make_program(coord)
    make_program(other)
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    plan2 = CurriculumPlan(program_id=program.id, version=2, name='Plan 2', is_current=False)
    db.session.add_all([plan, plan2])
    db.session.flush()
    math = Subject(plan_id=plan.id, name='Matemáticas', key='MAT', credits=5,
                   suggested_semester=1, kind='required', sequence=0)
    db.session.add(math)
    db.session.flush()
    period = make_academic_period()
    student = make_user('student')
    up = enroll(student, program, admission_status='enrolled')
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': 'active', 'curriculum_plan_id': plan.id, 'current_semester': 1})
    db.session.expire(up)
    group = group_svc.save_group(program.id, CourseGroupIn(
        subject_id=math.id, academic_period_id=period.id, group_code='A', capacity=5,
        teacher_id=coord.id), coord.id)
    enroll_svc.enroll(group.id, up.id, coord.id)
    grant(coord.role, *VIEW)
    grant(other.role, *VIEW)
    return {'coord': coord, 'other': other, 'student': student, 'up': up,
            'plan': plan, 'plan2': plan2, 'program': program}


def _base(w):
    return f"/students/{w['student'].uuid}/record/load"


def _manage(w):
    grant(w['coord'].role, 'curriculum.page.manage')


def test_fragment_for_coordinator(world, login):
    _manage(world)
    res = login(world['coord']).get(_base(world), headers=HX)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Matemáticas' in html
    assert 'Versión 1' in html
    assert 'loadPlanForm' in html


def test_non_htmx_redirects_to_record_tab(world, login):
    res = login(world['coord']).get(_base(world))
    assert res.status_code == 302
    assert res.headers['Location'].endswith(f"/students/{world['student'].uuid}/record?tab=carga")


def test_out_of_scope_is_404(world, login):
    assert login(world['other']).get(_base(world), headers=HX).status_code == 404


def test_plan_form_hidden_without_manage_permission(world, login):
    res = login(world['coord']).get(_base(world), headers=HX)
    assert res.status_code == 200
    assert 'loadPlanForm' not in res.get_data(as_text=True)


def test_change_plan_requires_reason(world, login):
    _manage(world)
    res = login(world['coord']).post(
        _base(world) + '/plan', headers=HX,
        data={'plan_id': world['plan2'].id, 'reason': '  '})
    assert res.status_code == 400
    db.session.expire_all()
    assert db.session.get(UserProgram, world['up'].id).curriculum_plan_id == world['plan'].id


def test_change_plan_ok(world, login):
    _manage(world)
    from app.models.course_enrollment import CourseEnrollment
    CourseEnrollment.query.filter_by(user_program_id=world['up'].id).update({'status': 'dropped'})
    res = login(world['coord']).post(
        _base(world) + '/plan', headers=HX,
        data={'plan_id': world['plan2'].id, 'reason': 'Cambio de retícula'})
    assert res.status_code == 200
    assert 'Versión 2' in res.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(UserProgram, world['up'].id).curriculum_plan_id == world['plan2'].id


def test_change_plan_without_permission_is_403(world, login):
    res = login(world['coord']).post(
        _base(world) + '/plan', headers=HX,
        data={'plan_id': world['plan2'].id, 'reason': 'x'})
    assert res.status_code == 403


def test_change_plan_with_enrolled_courses_is_refused(world, login):
    _manage(world)
    res = login(world['coord']).post(
        _base(world) + '/plan', headers=HX,
        data={'plan_id': world['plan2'].id, 'reason': 'Cambio'})
    assert res.status_code == 400
    db.session.expire_all()
    assert db.session.get(UserProgram, world['up'].id).curriculum_plan_id != world['plan2'].id

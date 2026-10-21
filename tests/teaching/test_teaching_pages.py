"""Phase 6B1: Docencia -> Mis grupos (own groups only, read-only roster)."""

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

PERM = 'teaching.page.my_groups'


def _group(world, subject, teacher, code='A'):
    data = CourseGroupIn(subject_id=subject.id, academic_period_id=world['period'].id,
                         group_code=code, capacity=10, teacher_id=teacher.id)
    return group_svc.save_group(world['program'].id, data, world['coord'].id)


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    other_coord = make_user('program_admin')
    program = make_program(coord)
    make_program(other_coord)
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    math = Subject(plan_id=plan.id, name='Matemáticas', key='MAT', credits=5,
                   suggested_semester=1, kind='required', sequence=0)
    algo = Subject(plan_id=plan.id, name='Algoritmos', key='ALG', credits=5,
                   suggested_semester=1, kind='required', sequence=1)
    db.session.add_all([math, algo])
    db.session.flush()
    period = make_academic_period()
    teacher = make_user('teacher')
    other_teacher = make_user('teacher')
    loner = make_user('teacher')
    grant(teacher.role, PERM)
    grant(coord.role, PERM)
    grant(other_coord.role, PERM)
    w = {'coord': coord, 'other_coord': other_coord, 'program': program, 'plan': plan,
         'period': period, 'teacher': teacher, 'other_teacher': other_teacher,
         'loner': loner}
    w['mine'] = _group(w, math, teacher)
    w['theirs'] = _group(w, algo, other_teacher)
    student = make_user('student', first_name='Ana', last_name='Zapata', control_number='C-001')
    up = enroll(student, program, admission_status='enrolled')
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': 'active', 'curriculum_plan_id': plan.id, 'current_semester': 1})
    db.session.expire(up)
    enroll_svc.enroll(w['mine'].id, up.id, coord.id)
    return w


def test_teacher_sees_only_own_groups(world, login):
    res = login(world['teacher']).get('/teaching/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Matemáticas' in html
    assert 'Algoritmos' not in html
    assert str(world['mine'].uuid) in html


def test_user_without_groups_sees_empty_state(world, login):
    res = login(world['loner']).get('/teaching/')
    assert res.status_code == 200
    assert 'No tienes grupos asignados en este periodo.' in res.get_data(as_text=True)


def test_without_permission_is_refused(world, login):
    client = login(make_user('social_service'))
    assert client.get('/teaching/', headers={'HX-Request': 'true'}).status_code == 403
    assert client.get('/teaching/').status_code == 302


def test_teacher_opens_own_group_roster(world, login):
    res = login(world['teacher']).get(f"/teaching/groups/{world['mine'].uuid}")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Zapata' in html and 'C-001' in html and 'Ordinario' in html


def test_teacher_opening_anothers_group_is_404(world, login):
    assert login(world['teacher']).get(f"/teaching/groups/{world['theirs'].uuid}").status_code == 404


def test_coordinator_in_scope_opens_group(world, login):
    res = login(world['coord']).get(f"/teaching/groups/{world['theirs'].uuid}")
    assert res.status_code == 200


def test_coordinator_out_of_scope_is_404(world, login):
    assert login(world['other_coord']).get(f"/teaching/groups/{world['mine'].uuid}").status_code == 404


def test_unknown_group_uuid_is_404(world, login):
    assert login(world['teacher']).get(
        '/teaching/groups/00000000-0000-4000-8000-000000000000').status_code == 404


def test_bad_period_param_is_404(world, login):
    assert login(world['teacher']).get('/teaching/?period=zzz').status_code == 404

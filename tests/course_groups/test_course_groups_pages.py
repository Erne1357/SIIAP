"""Phase 6B1, Task 5: "Carga académica" fragments and teacher accounts."""

import json

import pytest
from flask import g

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.course_group import CourseGroup
from app.models.curriculum_plan import CurriculumPlan
from app.models.email_queue import EmailQueue
from app.models.password_reset_token import PasswordResetToken
from app.models.subject import Subject
from app.models.user import User
from app.services import teacher_service
from app.services.errors import DomainError
from tests.support.factories import (
    enroll, get_or_create_role, grant, make_academic_period, make_program, make_user,
)

HX = {'HX-Request': 'true'}
MANAGE = 'course_groups.page.manage'


def _switch(login, user):
    """Log in as another user: the test app context keeps flask-login's cached user."""
    if hasattr(g, '_login_user'):
        del g._login_user
    return login(user)


def _flash(res):
    return json.loads(res.headers['HX-Trigger'])['siiap:flash']['message']


def _student(program, plan, name):
    user = make_user('student', first_name=name, last_name='Alumno')
    up = enroll(user, program, 'enrolled')
    up.academic_status = 'active'
    up.curriculum_plan_id = plan.id
    up.current_semester = 1
    db.session.flush()
    return up


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    other = make_user('program_admin')
    program = make_program(coord)
    make_program(other)
    period = make_academic_period()
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    subject = Subject(plan_id=plan.id, key='M1', name='Matemáticas', credits=5,
                      suggested_semester=1, kind='required', sequence=1)
    db.session.add(subject)
    db.session.flush()
    teacher = make_user('teacher', first_name='Tomás', last_name='Docente')
    grant(coord.role, MANAGE)
    grant(other.role, MANAGE)
    ups = [_student(program, plan, n) for n in ('Ana', 'Beto')]
    return {'coord': coord, 'other': other, 'program': program, 'period': period,
            'plan': plan, 'subject': subject, 'teacher': teacher, 'ups': ups}


def _group_form(w, **over):
    data = {'subject_id': w['subject'].id, 'academic_period_id': w['period'].id,
            'group_code': 'A', 'capacity': '2', 'teacher_id': w['teacher'].id,
            'location': 'Aula 3', 'schedule': 'Lunes 10:00'}
    data.update(over)
    return data


def _make_group(client, w, **over):
    res = client.post(f"/course-groups/program/{w['program'].id}", data=_group_form(w, **over),
                      headers=HX)
    assert res.status_code == 200, res.get_data(as_text=True)
    return CourseGroup.query.order_by(CourseGroup.id.desc()).first()


# -- scope and permission ------------------------------------------------------

def test_program_fragment_for_coordinator(world, login):
    res = login(world['coord']).get(f"/course-groups/program/{world['program'].id}", headers=HX)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Nuevo grupo' in html and 'Sin grupos en este periodo' in html


def test_other_program_coordinator_gets_404_on_fragment(world, login):
    res = login(world['other']).get(f"/course-groups/program/{world['program'].id}", headers=HX)
    assert res.status_code == 404


def test_other_program_coordinator_gets_404_on_group(world, login):
    group = _make_group(login(world['coord']), world)
    other = _switch(login, world['other'])
    assert other.get(f'/course-groups/{group.uuid}', headers=HX).status_code == 404
    assert other.post(f'/course-groups/{group.uuid}', data=_group_form(world),
                      headers=HX).status_code == 404
    assert other.post(f'/course-groups/{group.uuid}/enroll',
                      data={'user_program_id': world['ups'][0].id}, headers=HX).status_code == 404


def test_without_permission_is_403(world, login):
    nobody = make_user('student')
    res = login(nobody).get(f"/course-groups/program/{world['program'].id}", headers=HX)
    assert res.status_code == 403


# -- groups --------------------------------------------------------------------

def test_create_group_and_list_it(world, login):
    client = login(world['coord'])
    res = client.post(f"/course-groups/program/{world['program'].id}",
                      data=_group_form(world), headers=HX)
    assert res.status_code == 200
    assert _flash(res) == 'Grupo creado.'
    html = res.get_data(as_text=True)
    assert 'Matemáticas' in html and 'Aula 3' in html and 'Docente' in html
    assert CourseGroup.query.count() == 1


def test_group_detail_and_edit(world, login):
    client = login(world['coord'])
    group = _make_group(client, world)
    res = client.get(f'/course-groups/{group.uuid}', headers=HX)
    assert res.status_code == 200 and 'Sin estudiantes inscritos' in res.get_data(as_text=True)
    res = client.post(f'/course-groups/{group.uuid}', data=_group_form(world, capacity='5'),
                      headers=HX)
    assert res.status_code == 200 and _flash(res) == 'Grupo actualizado.'
    db.session.expire_all()
    assert db.session.get(CourseGroup, group.id).capacity == 5


def test_invalid_capacity_is_rejected(world, login):
    res = login(world['coord']).post(f"/course-groups/program/{world['program'].id}",
                                     data=_group_form(world, capacity='0'), headers=HX)
    assert res.status_code == 400
    assert CourseGroup.query.count() == 0


# -- enrolling -----------------------------------------------------------------

def test_enroll_and_drop(world, login):
    client = login(world['coord'])
    group = _make_group(client, world)
    up = world['ups'][0]
    res = client.post(f'/course-groups/{group.uuid}/enroll',
                      data={'user_program_id': up.id}, headers=HX)
    assert res.status_code == 200
    assert _flash(res) == 'Estudiante inscrito en el grupo.'
    html = res.get_data(as_text=True)
    assert 'Ordinario' in html and 'Ana' in html
    enrollment = CourseEnrollment.query.filter_by(user_program_id=up.id).one()

    res = client.post(f'/course-groups/{group.uuid}/drop/{enrollment.id}', headers=HX)
    assert res.status_code == 200 and _flash(res) == 'Estudiante quitado del grupo.'
    db.session.expire_all()
    assert db.session.get(CourseEnrollment, enrollment.id).status == 'dropped'


def test_drop_of_another_groups_enrollment_is_404(world, login):
    client = login(world['coord'])
    group_a = _make_group(client, world)
    group_b = _make_group(client, world, group_code='B')
    client.post(f'/course-groups/{group_a.uuid}/enroll',
                data={'user_program_id': world['ups'][0].id}, headers=HX)
    enrollment = CourseEnrollment.query.one()
    res = client.post(f'/course-groups/{group_b.uuid}/drop/{enrollment.id}', headers=HX)
    assert res.status_code == 404


def test_full_group_shows_spanish_error(world, login):
    client = login(world['coord'])
    group = _make_group(client, world, capacity='1')
    client.post(f'/course-groups/{group.uuid}/enroll',
                data={'user_program_id': world['ups'][0].id}, headers=HX)
    res = client.post(f'/course-groups/{group.uuid}/enroll',
                      data={'user_program_id': world['ups'][1].id}, headers=HX)
    assert res.status_code == 400
    assert _flash(res) == 'El grupo no tiene cupo.'


def test_enroll_semester_summary(world, login):
    client = login(world['coord'])
    _make_group(client, world, capacity='1')
    group = CourseGroup.query.one()
    res = client.post(
        f"/course-groups/program/{world['program'].id}/enroll-semester",
        data={'group_ids': [group.id], 'user_program_ids': [u.id for u in world['ups']],
              'period': world['period'].id},
        headers=HX)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Inscripciones realizadas: 1.' in html
    assert 'El grupo no tiene cupo.' in html
    assert CourseEnrollment.query.filter_by(status='enrolled').count() == 1


def test_enroll_semester_ignores_foreign_ids_and_needs_selection(world, login):
    client = login(world['coord'])
    res = client.post(f"/course-groups/program/{world['program'].id}/enroll-semester",
                      data={'group_ids': ['999'], 'user_program_ids': ['999']}, headers=HX)
    assert res.status_code == 400


# -- teachers ------------------------------------------------------------------

def test_create_teacher_new(world, app):
    get_or_create_role('teacher')
    actor = world['coord']
    user = teacher_service.create_teacher('Rosa', 'Maestra', 'Rosa@Escuela.test', actor.id)
    assert user.email == 'rosa@escuela.test' and user.role.name == 'teacher'
    assert user.is_internal and user.must_change_password
    assert PasswordResetToken.query.filter_by(user_id=user.id, purpose='set_password').count() == 1
    assert EmailQueue.query.filter_by(user_id=user.id).count() == 1


def test_create_teacher_reuses_existing_teacher(world):
    again = teacher_service.create_teacher('X', 'Y', world['teacher'].email.upper(),
                                           world['coord'].id)
    assert again.id == world['teacher'].id
    assert EmailQueue.query.count() == 0


def test_create_teacher_with_other_role_email_fails(world):
    with pytest.raises(DomainError) as exc:
        teacher_service.create_teacher('X', 'Y', world['coord'].email, world['coord'].id)
    assert str(exc.value) == ('No se pudo dar de alta al docente con ese correo. Si ya tiene '
                              'cuenta, elígelo de la lista de docentes.')


def test_teacher_choices_lists_teachers_first(world):
    ids = [u.id for u in teacher_service.teacher_choices()]
    assert ids[0] == world['teacher'].id
    assert world['coord'].id in ids


def test_teacher_route_requires_create_permission(world, login):
    data = {'first_name': 'Rosa', 'last_name': 'Maestra', 'email': 'rosa@escuela.test'}
    res = login(world['coord']).post('/course-groups/teachers', data=data, headers=HX)
    assert res.status_code == 403
    assert User.query.filter_by(email='rosa@escuela.test').count() == 0


def test_teacher_route_creates_and_returns_select(world, login):
    grant(world['coord'].role, 'teachers.page.create')
    data = {'first_name': 'Rosa', 'last_name': 'Maestra', 'email': 'rosa@escuela.test'}
    res = login(world['coord']).post('/course-groups/teachers', data=data, headers=HX)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    new = User.query.filter_by(email='rosa@escuela.test').one()
    assert 'id="groupTeacherField"' in html
    assert f'value="{new.id}" selected' in html
    assert 'Docente listo' in _flash(res)

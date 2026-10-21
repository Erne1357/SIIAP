"""Teacher dashboard and the student's "Mi carga académica" card (phase 6B1)."""

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.course_group import CourseGroup
from app.models.curriculum_plan import CurriculumPlan
from app.models.subject import Subject
from app.services.dashboard_service import DashboardService
from tests.support.factories import (
    enroll, grant, make_academic_period, make_program, make_user,
)


def _world():
    coord = make_user('program_admin')
    program = make_program(coord)
    plan = CurriculumPlan(program_id=program.id, version=1, name='v1', is_current=True)
    db.session.add(plan)
    db.session.flush()
    subject = Subject(plan_id=plan.id, key='MC-01', name='Cómputo Avanzado', credits=5,
                      suggested_semester=1, kind='required', sequence=1)
    other_subject = Subject(plan_id=plan.id, key='MC-02', name='Estadística', credits=5,
                            suggested_semester=1, kind='required', sequence=2)
    db.session.add_all([subject, other_subject])
    db.session.flush()
    return program, plan, subject, other_subject


def _group(program, period, subject, teacher, code='A', **kw):
    group = CourseGroup(program_id=program.id, academic_period_id=period.id,
                        subject_id=subject.id, group_code=code, teacher_id=teacher.id,
                        capacity=kw.pop('capacity', 10), **kw)
    db.session.add(group)
    db.session.flush()
    return group


def _enrollment(up, subject, period, group):
    db.session.add(CourseEnrollment(user_program_id=up.id, subject_id=subject.id,
                                    academic_period_id=period.id, course_group_id=group.id,
                                    attempt=1, attempt_type='ordinary', status='enrolled'))


def test_teacher_kind_and_context_list_only_own_active_groups(app):
    teacher = make_user('teacher')
    grant(teacher.role, 'teaching.page.my_groups')
    other = make_user('teacher')
    program, _plan, subject, subject2 = _world()
    active = make_academic_period('20271', is_active=True)
    past = make_academic_period('20263', is_active=False)
    mine = _group(program, active, subject, teacher, 'A', schedule='Lun 9-11', location='Aula 3')
    _group(program, active, subject2, other, 'B')          # someone else's
    _group(program, past, subject, teacher, 'C')           # other period
    up = enroll(make_user('student'), program, 'enrolled')
    _enrollment(up, subject, active, mine)
    db.session.commit()

    assert DashboardService.dashboard_kind(teacher) == 'teacher'
    ctx = DashboardService.build_dashboard_context(teacher)
    assert [g['group_code'] for g in ctx['teaching_groups']] == ['A']
    row = ctx['teaching_groups'][0]
    assert row['subject_name'] == 'Cómputo Avanzado'
    assert (row['enrolled'], row['capacity']) == (1, 10)
    assert row['schedule'] == 'Lun 9-11' and row['location'] == 'Aula 3'


def test_student_card_lists_active_period_load(app):
    program, _plan, subject, subject2 = _world()
    student = make_user('student')
    grant(student.role, 'course_enrollment.page.view_own')
    up = enroll(student, program, 'enrolled')
    teacher = make_user('teacher')
    active = make_academic_period('20271', is_active=True)
    past = make_academic_period('20263', is_active=False)
    _enrollment(up, subject, active, _group(program, active, subject, teacher, 'A'))
    _enrollment(up, subject2, past, _group(program, past, subject2, teacher, 'A'))
    db.session.commit()

    ctx = DashboardService.build_dashboard_context(student)
    assert [i['subject'].name for i in ctx['academic_load']] == ['Cómputo Avanzado']


def test_student_card_hidden_without_permission(app):
    program, *_ = _world()
    student = make_user('student')
    enroll(student, program, 'enrolled')
    make_academic_period('20271', is_active=True)
    db.session.commit()
    assert DashboardService.build_dashboard_context(student)['academic_load'] == []


def test_teacher_dashboard_renders(app, login):
    program, _plan, subject, _s2 = _world()
    teacher = make_user('teacher')
    grant(teacher.role, 'teaching.page.my_groups')
    active = make_academic_period('20271', is_active=True)
    _group(program, active, subject, teacher, 'A', location='Aula 3')
    db.session.commit()

    resp = login(teacher).get('/user/dashboard')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Cómputo Avanzado' in html and 'Mis grupos del periodo' in html


def test_student_dashboard_shows_load_card(app, login):
    program, _plan, subject, _s2 = _world()
    teacher = make_user('teacher')
    student = make_user('student')
    grant(student.role, 'permanence.api.view_status', 'course_enrollment.page.view_own')
    up = enroll(student, program, 'enrolled')
    active = make_academic_period('20271', is_active=True)
    _enrollment(up, subject, active, _group(program, active, subject, teacher, 'A', location='Aula 3'))
    db.session.commit()

    resp = login(student).get('/user/dashboard')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Mi carga académica' in html and 'Cómputo Avanzado' in html

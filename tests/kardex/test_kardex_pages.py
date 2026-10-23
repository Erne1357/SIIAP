"""Phase 6B2: "Mi kardex" page and the record's "Kardex" tab."""

import pytest

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.curriculum_plan import CurriculumPlan
from app.models.subject import Subject
from app.models.user_program import UserProgram
from tests.support.factories import (
    enroll, grant, make_academic_period, make_program, make_user,
)

HX = {'HX-Request': 'true'}
VIEW = ('students.page.view_record', 'students.api.view_record')


def _subject(plan, name, kind='required', semester=1, key=None):
    s = Subject(plan_id=plan.id, name=name, kind=kind, key=key, credits=5,
                suggested_semester=None if kind == 'elective' else semester, sequence=0)
    db.session.add(s)
    db.session.flush()
    return s


def _attempt(up, subject, period, *, grade=None, mark=None, result=None, slot=None):
    row = CourseEnrollment(
        user_program_id=up.id, subject_id=subject.id, academic_period_id=period.id,
        slot_subject_id=slot.id if slot else None, attempt=1, attempt_type='ordinary',
        status='graded', grade=grade, grade_mark=mark, result=result)
    db.session.add(row)
    db.session.flush()
    return row


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    other = make_user('program_admin')
    program = make_program(coord)
    make_program(other)
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    math = _subject(plan, 'Matemáticas', key='MAT')
    algo = _subject(plan, 'Algoritmos', semester=2, key='ALG')
    slot = _subject(plan, 'Optativa I', kind='elective_slot', semester=2)
    ml = _subject(plan, 'Aprendizaje automático', kind='elective', key='ML')
    p1, p2 = make_academic_period(), make_academic_period()
    student = make_user('student')
    up = enroll(student, program, admission_status='enrolled')
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': 'active', 'curriculum_plan_id': plan.id, 'current_semester': 2})
    db.session.expire(up)
    _attempt(up, math, p1, mark='NP', result='failed')
    _attempt(up, ml, p2, grade=80, result='passed', slot=slot)
    grant(student.role, 'kardex.page.view_own')
    grant(coord.role, *VIEW)
    grant(other.role, *VIEW)
    return {'coord': coord, 'other': other, 'student': student, 'up': up,
            'program': program, 'plan': plan, 'algo': algo}


def test_student_sees_own_kardex(world, login):
    res = login(world['student']).get('/kardex/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Mi kardex' in html
    assert 'Matemáticas' in html
    assert 'NP' in html
    assert '80.00' in html          # average of passed subjects (NP excluded)
    assert 'Versión 1' in html


def test_slot_row_shows_the_elective_taken(world, login):
    html = login(world['student']).get('/kardex/').get_data(as_text=True)
    assert 'Optativa I' in html
    assert 'Aprendizaje automático' in html


def test_foreign_program_param_is_404(world, login):
    other_student = make_user('student')
    grant(other_student.role, 'kardex.page.view_own')
    foreign = make_program(world['coord'], slug='otro-prog')
    enroll(other_student, foreign, admission_status='enrolled')
    res = login(world['student']).get(f'/kardex/?program={foreign.id}')
    assert res.status_code == 404


def test_own_program_param_is_200(world, login):
    res = login(world['student']).get(f"/kardex/?program={world['program'].id}")
    assert res.status_code == 200


def test_student_without_plan_sees_empty_state(world, login):
    UserProgram.query.filter_by(id=world['up'].id).update({'curriculum_plan_id': None})
    db.session.expire_all()
    res = login(world['student']).get('/kardex/')
    assert res.status_code == 200
    assert 'Sin plan de estudios' in res.get_data(as_text=True)


def _tab(w):
    return f"/students/{w['student'].uuid}/record/kardex"


def test_record_tab_for_coordinator(world, login):
    res = login(world['coord']).get(_tab(world), headers=HX)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Matemáticas' in html and 'NP' in html


def test_record_tab_non_htmx_redirects(world, login):
    res = login(world['coord']).get(_tab(world))
    assert res.status_code == 302
    assert res.headers['Location'].endswith(f"/students/{world['student'].uuid}/record?tab=kardex")


def test_record_tab_out_of_scope_is_404(world, login):
    assert login(world['other']).get(_tab(world), headers=HX).status_code == 404

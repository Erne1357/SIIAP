"""Phase 6B3: grade history import pages."""
import io
from datetime import date, timedelta

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
PERM = 'grades.page.import_history'
HEAD = 'no_control,clave_materia,periodo,calificacion,hueco\n'


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    other = make_user('program_admin')
    program = make_program(coord)
    other_program = make_program(other)
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    db.session.add(Subject(plan_id=plan.id, name='Matemáticas', kind='required', key='MAT',
                           credits=5, suggested_semester=1, sequence=0))
    period = make_academic_period('20241', is_active=False)
    period.start_date = date.today() - timedelta(days=400)
    period.end_date = period.start_date + timedelta(days=120)
    student = make_user('student', control_number='21110001')
    up = enroll(student, program, admission_status='enrolled')
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': 'active', 'curriculum_plan_id': plan.id})
    stranger = make_user('student', control_number='99990000')
    enroll(stranger, other_program, admission_status='enrolled')
    grant(coord.role, PERM)
    db.session.flush()
    return {'coord': coord, 'other': other, 'up': up}


def _upload(client, text, name='h.csv'):
    return client.post('/grade-import/preview', headers=HX,
                       data={'file': (io.BytesIO(text.encode()), name)},
                       content_type='multipart/form-data')


def test_requires_permission(world, login):
    res = login(make_user('student')).get('/grade-import/')
    assert res.status_code in (302, 403)


def test_index_and_template(world, login):
    c = login(world['coord'])
    assert 'Importar historial' in c.get('/grade-import/').get_data(as_text=True)
    res = c.get('/grade-import/template.csv')
    assert res.mimetype == 'text/csv'
    assert 'plantilla_historial.csv' in res.headers['Content-Disposition']
    assert res.get_data(as_text=True).startswith('no_control')


def test_preview_shows_valid_and_error_rows(world, login):
    res = _upload(login(world['coord']),
                  HEAD + '21110001,MAT,20241,80,\n21110001,XYZ,20241,80,\n')
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert 'Válida' in html and 'Error' in html
    assert 'no existe en el plan' in html
    assert 'name="csv_text"' in html


def test_empty_file_is_refused(world, login):
    res = _upload(login(world['coord']), '')
    assert res.status_code == 400
    assert 'siiap:flash' in res.headers.get('HX-Trigger', '')


def test_execute_writes_rows(world, login):
    res = login(world['coord']).post('/grade-import/execute', headers=HX,
                                     data={'csv_text': HEAD + '21110001,MAT,20241,80,\n'})
    assert res.status_code == 200
    assert 'Importadas' in res.get_data(as_text=True)
    assert CourseEnrollment.query.filter_by(user_program_id=world['up'].id).count() == 1


def test_execute_revalidates_scope(world, login):
    res = login(world['coord']).post('/grade-import/execute', headers=HX,
                                     data={'csv_text': HEAD + '99990000,MAT,20241,80,\n'})
    assert res.status_code == 200
    assert CourseEnrollment.query.count() == 0


def test_out_of_scope_coordinator_sees_not_found(world, login):
    grant(world['other'].role, PERM)
    html = _upload(login(world['other']),
                   HEAD + '21110001,MAT,20241,80,\n').get_data(as_text=True)
    assert 'Alumno no encontrado.' in html

"""Phase 6B1 task 4: study-plan page and its HTMX fragments."""

import json

import pytest

from app import db
from app.models.curriculum_plan import CurriculumPlan
from app.models.subject import Subject
from tests.support.factories import grant, make_program, make_user

HX = {'HX-Request': 'true'}
PERM = 'curriculum.page.manage'


def _plan(program, version=1, current=True, name='Plan 2024'):
    plan = CurriculumPlan(program_id=program.id, version=version, is_current=current, name=name)
    db.session.add(plan)
    db.session.flush()
    return plan


def _subject(plan, name, key=None, credits=None, semester=None, kind='required', seq=1):
    subject = Subject(plan_id=plan.id, name=name, key=key, credits=credits,
                      suggested_semester=semester, kind=kind, sequence=seq)
    db.session.add(subject)
    db.session.flush()
    return subject


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    other = make_user('program_admin')
    admin = make_user('postgraduate_admin')
    nobody = make_user('student')
    program = make_program(coord, name='Maestría A')
    other_program = make_program(other, name='Maestría B')
    plan = _plan(program)
    other_plan = _plan(other_program, name='Plan B')
    algebra = _subject(plan, 'Álgebra', key='MAT1', credits=8, semester=1)
    _subject(plan, 'Seminario', semester=1, seq=2)
    _subject(plan, 'Optativa I', kind='elective_slot', semester=3, seq=3)
    _subject(plan, 'Cómputo verde', key='OPT1', credits=4, kind='elective', seq=4)
    for user in (coord, other, admin):
        grant(user.role, PERM)
    grant(admin.role, 'academic_periods.api.create')  # global program scope
    return {'coord': coord, 'other': other, 'admin': admin, 'nobody': nobody,
            'program': program, 'other_program': other_program, 'plan': plan,
            'other_plan': other_plan, 'algebra': algebra}


def _flash(res):
    return json.loads(res.headers['HX-Trigger'])['siiap:flash']['message']


def test_index_lists_only_own_programs(world, login):
    html = login(world['coord']).get('/curriculum/').get_data(as_text=True)
    assert 'Maestría A' in html
    assert 'Maestría B' not in html
    assert 'Vigente' in html
    assert 'Álgebra' in html


def test_index_other_program_is_404(world, login):
    res = login(world['coord']).get(f"/curriculum/?program={world['other_program'].id}")
    assert res.status_code == 404


def test_admin_sees_all_programs(world, login):
    client = login(world['admin'])
    html = client.get('/curriculum/').get_data(as_text=True)
    assert 'Maestría A' in html and 'Maestría B' in html
    res = client.get(f"/curriculum/?program={world['other_program'].id}")
    assert 'Plan B' in res.get_data(as_text=True)


def test_without_permission_is_refused(world, login):
    client = login(world['nobody'])
    assert client.get('/curriculum/').status_code == 302  # page: flash + redirect
    assert client.get('/curriculum/', headers=HX).status_code == 403
    res = client.post('/curriculum/plans', data={'program_id': world['program'].id}, headers=HX)
    assert res.status_code == 403


def test_fragment_groups_and_marks_incomplete(world, login):
    res = login(world['coord']).get(f"/curriculum/plans/{world['plan'].id}", headers=HX)
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert 'Semestre 1' in html
    assert 'Huecos de optativa' in html
    assert 'Banco de optativas' in html
    assert html.count('Falta clave o créditos') == 1


def test_fragment_non_htmx_redirects_to_page(world, login):
    res = login(world['coord']).get(f"/curriculum/plans/{world['plan'].id}")
    assert res.status_code == 302
    assert '/curriculum/?program=' in res.headers['Location']


def test_fragment_other_program_plan_is_404(world, login):
    res = login(world['coord']).get(f"/curriculum/plans/{world['other_plan'].id}", headers=HX)
    assert res.status_code == 404


def test_create_version_copies_subjects(world, login):
    res = login(world['coord']).post(
        '/curriculum/plans', data={'program_id': world['program'].id}, headers=HX)
    assert res.status_code == 200
    assert 'Versión 2' in _flash(res)
    db.session.expire_all()
    new = CurriculumPlan.query.filter_by(program_id=world['program'].id, version=2).one()
    assert not new.is_current
    assert Subject.query.filter_by(plan_id=new.id).count() == 4


def test_create_version_other_program_is_404(world, login):
    res = login(world['coord']).post(
        '/curriculum/plans', data={'program_id': world['other_program'].id}, headers=HX)
    assert res.status_code == 404


def test_set_current_switches(world, login):
    client = login(world['coord'])
    client.post('/curriculum/plans', data={'program_id': world['program'].id}, headers=HX)
    new = CurriculumPlan.query.filter_by(program_id=world['program'].id, version=2).one()
    res = client.post(f'/curriculum/plans/{new.id}/current', headers=HX)
    assert res.status_code == 200
    db.session.expire_all()
    assert db.session.get(CurriculumPlan, new.id).is_current
    assert not db.session.get(CurriculumPlan, world['plan'].id).is_current


def test_create_subject(world, login):
    res = login(world['coord']).post(
        f"/curriculum/plans/{world['plan'].id}/subjects", headers=HX,
        data={'key': 'FIS1', 'name': 'Física', 'credits': '6', 'suggested_semester': '2',
              'kind': 'required'})
    assert res.status_code == 200
    assert _flash(res) == 'Materia agregada.'
    subject = Subject.query.filter_by(plan_id=world['plan'].id, key='FIS1').one()
    assert (subject.name, subject.credits, subject.suggested_semester) == ('Física', 6, 2)
    assert 'Física' in res.get_data(as_text=True)


def test_edit_subject(world, login):
    res = login(world['coord']).post(
        f"/curriculum/subjects/{world['algebra'].id}", headers=HX,
        data={'key': 'MAT1', 'name': 'Álgebra lineal', 'credits': '9', 'suggested_semester': '1',
              'kind': 'required'})
    assert res.status_code == 200
    db.session.expire_all()
    assert db.session.get(Subject, world['algebra'].id).name == 'Álgebra lineal'


def test_duplicate_key_is_spanish_error(world, login):
    res = login(world['coord']).post(
        f"/curriculum/plans/{world['plan'].id}/subjects", headers=HX,
        data={'key': 'MAT1', 'name': 'Otra', 'credits': '4', 'kind': 'required'})
    assert res.status_code == 400
    assert 'ya existe' in _flash(res)


def test_edit_subject_of_other_program_is_404(world, login):
    other_subject = _subject(world['other_plan'], 'Ajena', key='X1', credits=1)
    db.session.commit()
    res = login(world['coord']).post(
        f'/curriculum/subjects/{other_subject.id}', headers=HX, data={'name': 'Hack'})
    assert res.status_code == 404


def test_deactivate_hides_from_default_list(world, login):
    client = login(world['coord'])
    res = client.post(f"/curriculum/subjects/{world['algebra'].id}/deactivate", headers=HX)
    assert res.status_code == 200
    assert 'Álgebra' not in res.get_data(as_text=True).replace('Desactivar Álgebra', '')
    db.session.expire_all()
    assert db.session.get(Subject, world['algebra'].id).is_active is False

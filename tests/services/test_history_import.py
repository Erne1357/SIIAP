"""Phase 6B3: importing grade history from past periods, and correcting it."""

from datetime import date, timedelta

import pytest

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.curriculum_plan import CurriculumPlan
from app.models.subject import Subject
from app.models.user_program import UserProgram
from app.services import grading_service as grading
from app.services import history_import_service as imp
from app.services import kardex_service
from app.services.errors import DomainError, NotFoundError
from tests.support.factories import enroll, make_academic_period, make_program, make_user


def _subject(plan, key, kind='required', semester=1, credits=5):
    s = Subject(plan_id=plan.id, name=f'Materia {key}', kind=kind, key=key,
                credits=None if kind == 'elective_slot' else credits,
                suggested_semester=None if kind == 'elective' else semester, sequence=0)
    db.session.add(s)
    db.session.flush()
    return s


def _past(code, months_ago):
    """A finished period starting `months_ago` months back (older = smaller start)."""
    p = make_academic_period(code, is_active=False)
    p.start_date = date.today() - timedelta(days=30 * months_ago)
    p.end_date = p.start_date + timedelta(days=120)
    assert p.end_date < date.today()
    db.session.flush()
    return p


@pytest.fixture
def w(app):
    coord = make_user('program_admin')
    program = make_program(coord)
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    for key, kind, sem in (('MAT', 'required', 1), ('ALG', 'required', 1),
                           ('OP1', 'elective_slot', 2), ('OP2', 'elective_slot', 3),
                           ('ML', 'elective', None), ('IA', 'elective', None)):
        _subject(plan, key, kind=kind, semester=sem)
    student = make_user('student', control_number='21110001')
    up = enroll(student, program, admission_status='enrolled')
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': 'active', 'curriculum_plan_id': plan.id})
    db.session.expire(up)
    return {'coord': coord, 'program': program, 'plan': plan, 'up': up,
            'p1': _past('20241', 30), 'p2': _past('20243', 24), 'p3': _past('20251', 18),
            'scope': {program.id}}


def _csv(*lines, header='no_control,clave_materia,periodo,calificacion,hueco'):
    return '\n'.join((header,) + lines) + '\n'


def _rows(w, *lines, scope='default'):
    return imp.preview(_csv(*lines), w['scope'] if scope == 'default' else scope)['rows']


# ── Reading ──────────────────────────────────────────────────────────────────

def test_missing_headers_and_empty_file(w):
    with pytest.raises(DomainError, match='Faltan columnas: calificacion'):
        imp.preview('no_control,clave_materia,periodo\n1,2,3\n', None)
    with pytest.raises(DomainError, match='vacío'):
        imp.preview('', None)
    with pytest.raises(DomainError, match='no tiene filas'):
        imp.preview(_csv(), None)


def test_bom_and_case_are_tolerated(w):
    text = '﻿NO_CONTROL,Clave_Materia,Periodo,Calificacion\n21110001,mat,20241,85\n'
    assert imp.preview(text, None)['valid_count'] == 1


# ── Row rules ────────────────────────────────────────────────────────────────

def test_attempts_are_numbered_by_period_order(w):
    rows = _rows(w, '21110001,MAT,20251,80,', '21110001,MAT,20241,NP,', '21110001,MAT,20243,60,')
    assert [r['attempt_label'] for r in rows] == ['Especial', 'Ordinario', 'Repetición']
    assert all(not r['errors'] for r in rows)


def test_unknown_and_out_of_scope_students_look_the_same(w):
    other = make_program(make_user('program_admin'))
    stranger = make_user('student', control_number='99990000')
    enroll(stranger, other, admission_status='enrolled')
    rows = _rows(w, '00000000,MAT,20241,80,', '99990000,MAT,20241,80,')
    assert rows[0]['errors'] == rows[1]['errors'] == ['Alumno no encontrado.']


def test_an_empty_scope_sees_nobody(w):
    assert _rows(w, '21110001,MAT,20241,80,', scope=set())[0]['errors'] == ['Alumno no encontrado.']


@pytest.mark.parametrize('line, message', [
    ('21110001,XYZ,20241,80,', 'no existe en el plan'),
    ('21110001,OP1,20241,80,', 'hueco de optativa no se califica'),
    ('21110001,MAT,99999,80,', 'El periodo no existe.'),
    ('21110001,MAT,20241,101,', '0 a 100 o NP'),
    ('21110001,MAT,20241,,', 'Falta calificacion.'),
    ('21110001,MAT,20241,80,OP1', 'sólo aplica a optativas'),
])
def test_row_errors(w, line, message):
    errors = _rows(w, line)[0]['errors']
    assert any(message in e for e in errors), errors


def test_current_or_future_periods_are_refused(w):
    make_academic_period('20263', is_active=True)
    assert 'concluidos' in _rows(w, '21110001,MAT,20263,80,')[0]['errors'][0]


def test_more_than_three_attempts(w):
    p4 = _past('20253', 12)
    rows = _rows(w, '21110001,MAT,20241,50,', '21110001,MAT,20243,50,',
                 '21110001,MAT,20251,50,', f'21110001,MAT,{p4.code},90,')
    assert 'tres intentos' in rows[3]['errors'][0]


def test_a_duplicate_blocks_the_later_rows_of_that_subject(w):
    rows = _rows(w, '21110001,MAT,20241,50,', '21110001,MAT,20241,60,',
                 '21110001,MAT,20243,80,', '21110001,ALG,20243,80,')
    assert 'ese periodo' in rows[1]['errors'][0]
    assert rows[2]['errors'] == ['Corrige primero la fila 3 de esta materia.']
    assert not rows[3]['errors']


def test_a_dropped_row_in_that_period_is_refused(w):
    math = Subject.query.filter_by(plan_id=w['plan'].id, key='MAT').one()
    db.session.add(CourseEnrollment(user_program_id=w['up'].id, subject_id=math.id,
                                    academic_period_id=w['p1'].id, status='dropped'))
    db.session.flush()
    assert 'baja en ese periodo' in _rows(w, '21110001,MAT,20241,80,')[0]['errors'][0]


def test_semicolon_files_and_lowercase_keys(w):
    math = Subject.query.filter_by(plan_id=w['plan'].id, key='MAT').one()
    math.key = 'mat'
    db.session.flush()
    text = 'no_control;clave_materia;periodo;calificacion\n21110001;MAT;20241;85\n'
    assert imp.preview(text, None)['valid_count'] == 1


def test_nothing_after_a_pass(w):
    rows = _rows(w, '21110001,MAT,20241,80,', '21110001,MAT,20243,90,')
    assert 'ya está aprobada' in rows[1]['errors'][0]


def test_recorded_attempts_are_never_reordered(w):
    imp.execute(_csv('21110001,MAT,20243,50,'), w['coord'].id, w['scope'])
    rows = _rows(w, '21110001,MAT,20241,40,', '21110001,MAT,20251,90,')
    assert 'igual o posterior' in rows[0]['errors'][0]
    assert rows[1]['errors'] == ['Corrige primero la fila 2 de esta materia.']
    assert _rows(w, '21110001,MAT,20251,90,')[0]['attempt_label'] == 'Repetición'


# ── Electives ────────────────────────────────────────────────────────────────

def test_elective_slots_explicit_auto_and_repeat(w):
    rows = _rows(w, '21110001,ML,20241,50,OP2', '21110001,IA,20243,90,',
                 '21110001,ML,20251,85,')
    assert [r['slot'] for r in rows] == ['Materia OP2', 'Materia OP1', 'Materia OP2']
    assert all(not r['errors'] for r in rows)


def test_first_free_slot_and_exhaustion(w):
    rows = _rows(w, '21110001,ML,20241,80,', '21110001,IA,20243,80,')
    assert [r['slot'] for r in rows] == ['Materia OP1', 'Materia OP2']
    extra = _subject(w['plan'], 'BD', kind='elective')
    rows = _rows(w, '21110001,ML,20241,80,', '21110001,IA,20243,80,',
                 f'21110001,{extra.key},20251,80,')
    assert 'cubrió todas sus optativas' in rows[2]['errors'][0]


def test_taken_slot_is_refused(w):
    rows = _rows(w, '21110001,ML,20241,80,OP1', '21110001,IA,20243,80,OP1')
    assert 'ya está cubierto' in rows[1]['errors'][0]


# ── Execute ──────────────────────────────────────────────────────────────────

def test_execute_writes_graded_rows_without_group(w):
    summary = imp.execute(_csv('21110001,MAT,20241,NP,', '21110001,MAT,20243,85,',
                               '21110001,XYZ,20241,80,'), w['coord'].id, w['scope'])
    assert (summary['valid_count'], summary['error_count']) == (2, 1)
    rows = CourseEnrollment.query.filter_by(user_program_id=w['up'].id).order_by(
        CourseEnrollment.attempt).all()
    assert [(r.attempt_type, r.grade, r.grade_mark, r.result, r.status, r.course_group_id)
            for r in rows] == [('ordinary', None, 'NP', 'failed', 'graded', None),
                               ('repeat', 85, None, 'passed', 'graded', None)]
    assert rows[0].graded_by == w['coord'].id
    k = kardex_service.kardex(w['up'].id)
    assert k['average'] == 85.0 and all(
        a['imported'] for s in k['semesters'] for r in s['rows'] for a in r['attempts'])


def test_execute_revalidates_and_is_idempotent(w):
    text = _csv('21110001,MAT,20241,80,')
    imp.execute(text, w['coord'].id, w['scope'])
    again = imp.execute(text, w['coord'].id, w['scope'])
    assert again['valid_count'] == 0
    assert CourseEnrollment.query.filter_by(user_program_id=w['up'].id).count() == 1


def test_a_failed_special_flags_but_never_withdraws(w):
    summary = imp.execute(_csv('21110001,MAT,20241,50,', '21110001,MAT,20243,50,',
                               '21110001,MAT,20251,NP,'), w['coord'].id, w['scope'])
    assert summary['special_failed_count'] == 1
    assert summary['flagged_students'] == ['Prueba Usuario']
    assert db.session.get(UserProgram, w['up'].id).academic_status == 'active'


# ── Corrections of imported rows ─────────────────────────────────────────────

def test_coordinator_requests_correction_of_imported_row(w):
    imp.execute(_csv('21110001,MAT,20241,60,'), w['coord'].id, w['scope'])
    e = CourseEnrollment.query.filter_by(user_program_id=w['up'].id).one()

    with pytest.raises(NotFoundError):
        grading.request_correction(e.id, '75', 'x', make_user('program_admin').id)
    with pytest.raises(NotFoundError):
        grading.request_correction(e.id, '75', 'x', w['coord'].id, group_id=1)

    c = grading.request_correction(e.id, '75', 'Error de captura', w['coord'].id)
    grading.decide_correction(c.id, True, None, make_user('postgraduate_admin').id)
    assert db.session.get(CourseEnrollment, e.id).result == 'passed'

"""Phase 6B2 domain rules: actas, the special-attempt rule, corrections and the kardex."""

from datetime import date, timedelta

import pytest

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.course_group import CourseGroup
from app.models.curriculum_plan import CurriculumPlan
from app.models.subject import Subject
from app.models.user_program import UserProgram
from app.schemas.curriculum import CourseGroupIn
from app.services import course_enrollment_service as enroll_svc
from app.services import course_group_service as group_svc
from app.services import grading_service as grading
from app.services import kardex_service
from app.services import permanence_service
from app.services.errors import DomainError
from app.utils.datetime_utils import now_local
from tests.support.factories import enroll, make_academic_period, make_program, make_user


def _subject(plan, name, kind='required', semester=1, credits=5):
    s = Subject(plan_id=plan.id, name=name, kind=kind, credits=credits, key=name[:3].upper(),
                suggested_semester=None if kind == 'elective' else semester, sequence=0)
    db.session.add(s)
    db.session.flush()
    return s


@pytest.fixture
def w(app):
    coord = make_user('program_admin')
    program = make_program(coord, duration_semesters=2)
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    subjects = {
        'math': _subject(plan, 'Matemáticas'),
        'algo': _subject(plan, 'Algoritmos', semester=2),
        'slot': _subject(plan, 'Optativa I', kind='elective_slot', semester=2, credits=None),
        'ml': _subject(plan, 'Aprendizaje', kind='elective', credits=4),
    }
    return {'coord': coord, 'teacher': make_user('teacher'), 'program': program,
            'plan': plan, 's': subjects, 'period': make_academic_period()}


def _student(w):
    up = enroll(make_user('student'), w['program'], admission_status='enrolled')
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': 'active', 'curriculum_plan_id': w['plan'].id, 'current_semester': 1})
    db.session.expire(up)
    return up


def _group(w, key, period=None, code='A'):
    return group_svc.save_group(w['program'].id, CourseGroupIn(
        subject_id=w['s'][key].id, academic_period_id=(period or w['period']).id,
        group_code=code, capacity=30, teacher_id=w['teacher'].id), w['coord'].id)


def _graded(w, key, up, value, period=None, slot=None):
    """Enroll, capture and close a one-student acta."""
    group = _group(w, key, period=period, code=f'G{period.id if period else 0}')
    e = enroll_svc.enroll(group.id, up.id, w['coord'].id, slot_subject_id=slot)
    grading.save_draft(group.id, {e.id: value}, w['teacher'].id)
    grading.close_acta(group.id, w['teacher'].id)
    return db.session.get(CourseEnrollment, e.id)


# ── Values and window ────────────────────────────────────────────────────────

@pytest.mark.parametrize('raw, parsed', [('85', (85, None)), (' np ', (None, 'NP')),
                                         ('', None), ('0', (0, None))])
def test_parse_value(raw, parsed):
    assert grading.parse_value(raw) == parsed


@pytest.mark.parametrize('raw', ['101', '7.5', 'abc', '-1', '²', '1000'])
def test_parse_value_rejects(raw):
    with pytest.raises(DomainError, match='0 a 100 o NP'):
        grading.parse_value(raw)


def test_capture_window_and_extension(w):
    group = _group(w, 'math')
    today = now_local().date()
    assert grading.capture_open(group, today)                 # no dates: open

    w['period'].grade_capture_start = today - timedelta(days=10)
    w['period'].grade_capture_end = today - timedelta(days=1)
    assert not grading.capture_open(group, today)             # window over

    grading.extend_capture(group.id, today + timedelta(days=3), 'Incapacidad', w['coord'].id)
    assert grading.capture_open(db.session.get(CourseGroup, group.id), today)


# ── Acta ─────────────────────────────────────────────────────────────────────

def test_only_the_groups_teacher_captures(w):
    group = _group(w, 'math')
    e = enroll_svc.enroll(group.id, _student(w).id, w['coord'].id)

    with pytest.raises(DomainError, match='Grupo no encontrado.'):
        grading.save_draft(group.id, {e.id: '90'}, make_user('teacher').id)


def test_close_requires_every_grade_and_makes_them_final(w):
    group = _group(w, 'math')
    a = enroll_svc.enroll(group.id, _student(w).id, w['coord'].id)
    b = enroll_svc.enroll(group.id, _student(w).id, w['coord'].id)
    grading.save_draft(group.id, {a.id: '95'}, w['teacher'].id)

    with pytest.raises(DomainError, match='Faltan 1 calificaciones'):
        grading.close_acta(group.id, w['teacher'].id)

    grading.save_draft(group.id, {b.id: 'NP'}, w['teacher'].id)
    summary = grading.close_acta(group.id, w['teacher'].id)

    assert summary == {'graded': 2, 'withdrawn': [], 'to_review': []}
    assert db.session.get(CourseEnrollment, a.id).result == 'passed'
    assert db.session.get(CourseEnrollment, b.id).result == 'failed'
    assert db.session.get(CourseGroup, group.id).status == 'closed'
    with pytest.raises(DomainError, match='ya está cerrada'):
        grading.close_acta(group.id, w['teacher'].id)


def test_failing_special_withdraws_automatically(w):
    up = _student(w)
    periods = [make_academic_period(is_active=False) for _ in range(3)]
    for period in periods[:2]:
        _graded(w, 'math', up, '50', period=period)
    third = _graded(w, 'math', up, 'NP', period=periods[2])

    assert third.attempt_type == 'special'
    up = db.session.get(UserProgram, up.id)
    assert up.academic_status == 'withdrawn'
    assert 'Reprobó en especial: Matemáticas' in up.withdrawal_reason


def test_a_passed_subject_cannot_be_enrolled_again(w):
    up = _student(w)
    _graded(w, 'math', up, '80', period=make_academic_period(is_active=False))

    with pytest.raises(DomainError, match='La materia ya está aprobada.'):
        enroll_svc.enroll(_group(w, 'math', code='Z').id, up.id, w['coord'].id)


# ── Corrections ──────────────────────────────────────────────────────────────

def test_correction_flow(w):
    up = _student(w)
    e = _graded(w, 'math', up, '60', period=make_academic_period(is_active=False))
    admin = make_user('postgraduate_admin')

    with pytest.raises(DomainError, match='igual a la actual'):
        grading.request_correction(e.id, '60', 'x', w['teacher'].id)
    c = grading.request_correction(e.id, '75', 'Error de captura', w['teacher'].id)
    with pytest.raises(DomainError, match='pendiente'):
        grading.request_correction(e.id, '80', 'otra', w['teacher'].id)
    with pytest.raises(DomainError, match='motivo del rechazo'):
        grading.decide_correction(c.id, False, '', admin.id)

    result = grading.decide_correction(c.id, True, None, admin.id)

    e = db.session.get(CourseEnrollment, e.id)
    assert (e.grade, e.result) == (75, 'passed')
    assert result['review_withdrawal'] is False


def test_correcting_a_special_flags_the_withdrawal_but_keeps_it(w):
    up = _student(w)
    periods = [make_academic_period(is_active=False) for _ in range(3)]
    for period in periods[:2]:
        _graded(w, 'math', up, '40', period=period)
    special = _graded(w, 'math', up, '60', period=periods[2])
    c = grading.request_correction(special.id, '71', 'Sumé mal', w['teacher'].id)

    result = grading.decide_correction(c.id, True, None, make_user('postgraduate_admin').id)

    assert result['review_withdrawal'] is True
    assert db.session.get(UserProgram, up.id).academic_status == 'withdrawn'


# ── Kardex ───────────────────────────────────────────────────────────────────

def test_kardex_average_credits_slots_and_completion(w):
    up = _student(w)
    p1, p2, p3 = (make_academic_period(is_active=False) for _ in range(3))
    _graded(w, 'math', up, 'NP', period=p1)
    _graded(w, 'math', up, '90', period=p2)
    _graded(w, 'algo', up, '80', period=p2)

    k = kardex_service.kardex(up.id)
    assert (k['passed_count'], k['total_count']) == (2, 3)
    assert k['average'] == 85.0                      # NP never enters
    assert (k['credits_earned'], k['credits_total']) == (10, 10)
    assert not k['complete']
    assert permanence_service.graduation_suggested(db.session.get(UserProgram, up.id)) is False

    _graded(w, 'ml', up, '70', period=p3, slot=w['s']['slot'].id)

    k = kardex_service.kardex(up.id)
    slot_row = next(r for s in k['semesters'] for r in s['rows'] if r['slot'] is not None)
    assert slot_row['taken_subject'].name == 'Aprendizaje' and slot_row['credits'] == 4
    assert k['complete'] and k['average'] == 80.0 and k['progress'] == 100
    assert permanence_service.graduation_suggested(db.session.get(UserProgram, up.id)) is True


def test_correction_must_belong_to_the_url_group(w):
    up = _student(w)
    e = _graded(w, 'math', up, '60', period=make_academic_period(is_active=False))
    other = _group(w, 'algo', code='X')

    with pytest.raises(DomainError, match='Calificación no encontrada.'):
        grading.request_correction(e.id, '75', 'x', w['teacher'].id, group_id=other.id)


def test_approval_is_refused_when_the_grade_changed(w):
    up = _student(w)
    e = _graded(w, 'math', up, '60', period=make_academic_period(is_active=False))
    c = grading.request_correction(e.id, '75', 'x', w['teacher'].id)
    CourseEnrollment.query.filter_by(id=e.id).update({'grade': 62})

    with pytest.raises(DomainError, match='cambió desde la solicitud'):
        grading.decide_correction(c.id, True, None, make_user('postgraduate_admin').id)


def test_failed_special_of_a_graduate_goes_to_review(w):
    up = _student(w)
    periods = [make_academic_period(is_active=False) for _ in range(3)]
    for period in periods[:2]:
        _graded(w, 'math', up, '50', period=period)
    group = _group(w, 'math', period=periods[2], code='S')
    e = enroll_svc.enroll(group.id, up.id, w['coord'].id)
    UserProgram.query.filter_by(id=up.id).update({'academic_status': 'graduated'})
    grading.save_draft(group.id, {e.id: '40'}, w['teacher'].id)

    summary = grading.close_acta(group.id, w['teacher'].id)

    assert summary['withdrawn'] == [] and len(summary['to_review']) == 1
    assert db.session.get(UserProgram, up.id).academic_status == 'graduated'


def test_a_retired_subject_does_not_block_completion(w):
    up = _student(w)
    p1 = make_academic_period(is_active=False)
    _graded(w, 'math', up, '50', period=p1)
    Subject.query.filter_by(id=w['s']['math'].id).update({'is_active': False})
    for key in ('algo',):
        _graded(w, key, up, '90', period=make_academic_period(is_active=False))
    _graded(w, 'ml', up, '80', period=make_academic_period(is_active=False),
            slot=w['s']['slot'].id)

    assert kardex_service.kardex(up.id)['complete'] is True

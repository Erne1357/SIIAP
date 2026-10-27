"""Phase 6B1 domain rules: study plans, course groups and the academic load."""

import pytest

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.curriculum_plan import CurriculumPlan
from app.models.subject import Subject
from app.models.user_history import UserHistory
from app.models.user_program import UserProgram
from app.schemas.curriculum import CourseGroupIn, SubjectIn
from app.services import course_enrollment_service as enroll_svc
from app.services import course_group_service as group_svc
from app.services import curriculum_service as plan_svc
from app.services import teaching_scope_service as teach_svc
from app.services.errors import DomainError
from tests.support.factories import enroll, make_academic_period, make_program, make_user


def _subject(plan, name, kind='required', semester=1, key=None):
    s = Subject(plan_id=plan.id, name=name, kind=kind, key=key, credits=5,
                suggested_semester=None if kind == 'elective' else semester, sequence=0)
    db.session.add(s)
    db.session.flush()
    return s


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    program = make_program(coord)
    plan = CurriculumPlan(program_id=program.id, version=1, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    period = make_academic_period()
    subjects = {
        'math': _subject(plan, 'Matemáticas', key='MAT'),
        'algo': _subject(plan, 'Algoritmos', semester=2, key='ALG'),
        'slot1': _subject(plan, 'Optativa I', kind='elective_slot', semester=2),
        'slot2': _subject(plan, 'Optativa II', kind='elective_slot', semester=3),
        'ml': _subject(plan, 'Aprendizaje automático', kind='elective', key='ML'),
        'nlp': _subject(plan, 'Lenguaje natural', kind='elective', key='NLP'),
    }
    teacher = make_user('teacher')
    return {'coord': coord, 'program': program, 'plan': plan, 'period': period,
            's': subjects, 'teacher': teacher}


def _student(w, status='active'):
    up = enroll(make_user('student'), w['program'], admission_status='enrolled')
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': status, 'curriculum_plan_id': w['plan'].id, 'current_semester': 1})
    db.session.expire(up)
    return up


def _group(w, subject_key, code='A', capacity=30, teacher=None, period=None):
    data = CourseGroupIn(subject_id=w['s'][subject_key].id,
                         academic_period_id=(period or w['period']).id,
                         group_code=code, capacity=capacity,
                         teacher_id=(teacher or w['teacher']).id)
    return group_svc.save_group(w['program'].id, data, w['coord'].id)


# ── Plans ────────────────────────────────────────────────────────────────────

def test_new_version_copies_subjects_and_only_one_is_current(world):
    v2 = plan_svc.create_version(world['program'].id, world['coord'].id)
    assert v2.version == 2 and not v2.is_current
    assert len(plan_svc.subjects_of(v2.id)) == len(world['s'])

    plan_svc.set_current(v2.id, world['coord'].id)

    current = CurriculumPlan.query.filter_by(program_id=world['program'].id, is_current=True).all()
    assert [p.id for p in current] == [v2.id]


def test_subject_key_is_unique_within_a_version(world):
    with pytest.raises(DomainError, match='ya existe'):
        plan_svc.save_subject(world['plan'].id, SubjectIn(name='Otra', key='MAT'),
                              world['coord'].id)


def test_change_student_plan_requires_reason_and_same_program(world):
    up = _student(world)
    other = CurriculumPlan(program_id=make_program().id, version=1, name='X', is_current=True)
    db.session.add(other)
    db.session.flush()
    v2 = plan_svc.create_version(world['program'].id, world['coord'].id)

    with pytest.raises(DomainError, match='El motivo es obligatorio.'):
        plan_svc.change_student_plan(up.id, v2.id, ' ', world['coord'].id)
    with pytest.raises(DomainError, match='otro programa'):
        plan_svc.change_student_plan(up.id, other.id, 'x', world['coord'].id)
    plan_svc.change_student_plan(up.id, v2.id, 'Cambio de retícula', world['coord'].id)

    assert db.session.get(UserProgram, up.id).curriculum_plan_id == v2.id


# ── Groups ───────────────────────────────────────────────────────────────────

def test_a_slot_cannot_be_offered_as_a_group(world):
    with pytest.raises(DomainError, match='hueco de optativa'):
        _group(world, 'slot1')


def test_capacity_cannot_drop_below_enrolled(world):
    group = _group(world, 'math', capacity=2)
    enroll_svc.enroll(group.id, _student(world).id, world['coord'].id)
    enroll_svc.enroll(group.id, _student(world).id, world['coord'].id)

    data = CourseGroupIn(subject_id=world['s']['math'].id,
                         academic_period_id=world['period'].id, group_code='A', capacity=1)
    with pytest.raises(DomainError, match='no puede ser menor'):
        group_svc.save_group(world['program'].id, data, world['coord'].id, group_id=group.id)


# ── Enrollment ───────────────────────────────────────────────────────────────

def test_capacity_is_enforced(world):
    group = _group(world, 'math', capacity=1)
    enroll_svc.enroll(group.id, _student(world).id, world['coord'].id)

    with pytest.raises(DomainError, match='El grupo no tiene cupo.'):
        enroll_svc.enroll(group.id, _student(world).id, world['coord'].id)


def test_only_active_students_of_the_plan_enroll(world):
    group = _group(world, 'math')
    with pytest.raises(DomainError, match='baja definitiva'):
        enroll_svc.enroll(group.id, _student(world, status='withdrawn').id, world['coord'].id)

    stranger = _student(world)
    UserProgram.query.filter_by(id=stranger.id).update({'curriculum_plan_id': None})
    with pytest.raises(DomainError, match='versión del plan'):
        enroll_svc.enroll(group.id, stranger.id, world['coord'].id)


def test_attempts_are_ordinary_repeat_special_then_exhausted(world):
    up = _student(world)
    periods = [world['period']] + [make_academic_period(is_active=False) for _ in range(3)]
    types = []
    for i, period in enumerate(periods[:3]):
        group = _group(world, 'math', code=f'G{i}', period=period)
        types.append(enroll_svc.enroll(group.id, up.id, world['coord'].id).attempt_type)
    assert types == ['ordinary', 'repeat', 'special']

    fourth = _group(world, 'math', code='G3', period=periods[3])
    with pytest.raises(DomainError, match='Agotó los tres intentos'):
        enroll_svc.enroll(fourth.id, up.id, world['coord'].id)


def test_drop_keeps_the_row_frees_the_seat_and_does_not_count(world):
    group = _group(world, 'math', capacity=1)
    up = _student(world)
    e = enroll_svc.enroll(group.id, up.id, world['coord'].id)

    enroll_svc.drop(e.id, world['coord'].id)

    assert db.session.get(CourseEnrollment, e.id).status == 'dropped'
    assert enroll_svc.next_attempt(up.id, world['s']['math'].id) == 1
    again = enroll_svc.enroll(group.id, up.id, world['coord'].id)   # same row, same period
    assert again.id == e.id and again.status == 'enrolled'
    assert UserHistory.query.filter_by(action='course_dropped', user_program_id=up.id).count() == 1


def test_electives_fill_open_slots_once(world):
    up = _student(world)
    ml = _group(world, 'ml')
    nlp = _group(world, 'nlp')
    slot1, slot2 = world['s']['slot1'].id, world['s']['slot2'].id

    first = enroll_svc.enroll(ml.id, up.id, world['coord'].id, slot_subject_id=slot1)
    assert first.slot_subject_id == slot1
    with pytest.raises(DomainError, match='ya está cubierto'):
        enroll_svc.enroll(nlp.id, up.id, world['coord'].id, slot_subject_id=slot1)

    second = enroll_svc.enroll(nlp.id, up.id, world['coord'].id)   # picks the open slot
    assert second.slot_subject_id == slot2


def test_enroll_semester_reports_skipped_students(world):
    math = _group(world, 'math', capacity=1)
    algo = _group(world, 'algo')
    a, b = _student(world), _student(world)
    sem2 = _student(world)
    UserProgram.query.filter_by(id=sem2.id).update({'current_semester': 2})

    result = enroll_svc.enroll_semester([math.id, algo.id], [a.id, b.id, sem2.id],
                                        world['coord'].id)

    assert result['enrolled'] == 2          # a → math, sem2 → algo
    assert len(result['skipped']) == 1 and 'cupo' in result['skipped'][0]['reason']


def test_load_for_groups_by_period(world):
    up = _student(world)
    enroll_svc.enroll(_group(world, 'math').id, up.id, world['coord'].id)

    load = enroll_svc.load_for(up.id)

    assert len(load) == 1 and load[0]['period'].id == world['period'].id
    assert load[0]['items'][0]['subject'].name == 'Matemáticas'
    assert load[0]['items'][0]['group_code'] == 'A'


def test_teaching_scope_is_the_assignment_not_the_role(world):
    coord_teacher = world['coord']
    mine = _group(world, 'math', teacher=coord_teacher)
    _group(world, 'algo')                                   # taught by world['teacher']

    assert [g.id for g in teach_svc.groups_of(coord_teacher.id)] == [mine.id]
    assert teach_svc.can_view_group(world['teacher'], mine) is False
    assert teach_svc.can_view_group(coord_teacher, mine) is True


# ── Review fixes ─────────────────────────────────────────────────────────────

def test_repeating_an_elective_keeps_its_slot(world):
    up = _student(world)
    later = make_academic_period(is_active=False)
    first = enroll_svc.enroll(_group(world, 'ml').id, up.id, world['coord'].id,
                              slot_subject_id=world['s']['slot1'].id)
    again = enroll_svc.enroll(_group(world, 'ml', code='B', period=later).id, up.id,
                              world['coord'].id)

    assert again.slot_subject_id == first.slot_subject_id
    assert again.attempt_type == 'repeat'


def test_student_of_another_program_is_not_found(world):
    group = _group(world, 'math')
    foreign = enroll(make_user('student'), make_program(), admission_status='enrolled')

    with pytest.raises(DomainError, match='Estudiante no encontrado.'):
        enroll_svc.enroll(group.id, foreign.id, world['coord'].id)


def test_enroll_semester_rejects_groups_of_different_periods(world):
    a = _group(world, 'math')
    b = _group(world, 'math', code='B', period=make_academic_period(is_active=False))

    with pytest.raises(DomainError, match='mismo periodo'):
        enroll_svc.enroll_semester([a.id, b.id], [_student(world).id], world['coord'].id)


def test_an_older_version_can_become_current_again(world):
    v2 = plan_svc.create_version(world['program'].id, world['coord'].id)
    plan_svc.set_current(v2.id, world['coord'].id)
    plan_svc.set_current(world['plan'].id, world['coord'].id)

    assert plan_svc.current_plan(world['program'].id).id == world['plan'].id


def test_kind_of_a_subject_in_use_is_frozen(world):
    _group(world, 'math')
    with pytest.raises(DomainError, match='No se puede cambiar el tipo'):
        plan_svc.save_subject(world['plan'].id,
                              SubjectIn(name='Matemáticas', key='MAT', kind='elective'),
                              world['coord'].id, subject_id=world['s']['math'].id)


def test_plan_change_is_blocked_while_courses_are_enrolled(world):
    up = _student(world)
    enroll_svc.enroll(_group(world, 'math').id, up.id, world['coord'].id)
    v2 = plan_svc.create_version(world['program'].id, world['coord'].id)

    with pytest.raises(DomainError, match='materias inscritas'):
        plan_svc.change_student_plan(up.id, v2.id, 'Cambio', world['coord'].id)


def test_group_with_history_keeps_subject_and_period(world):
    group = _group(world, 'math')
    e = enroll_svc.enroll(group.id, _student(world).id, world['coord'].id)
    enroll_svc.drop(e.id, world['coord'].id)
    data = CourseGroupIn(subject_id=world['s']['algo'].id,
                         academic_period_id=world['period'].id, group_code='A', capacity=5)

    with pytest.raises(DomainError, match='No se puede cambiar la materia'):
        group_svc.save_group(world['program'].id, data, world['coord'].id, group_id=group.id)

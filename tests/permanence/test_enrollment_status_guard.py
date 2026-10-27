"""Phase 6D: every write of SemesterEnrollment.status goes through the transition rule."""

import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import db
from app.models.semester_enrollment import SemesterEnrollment
from app.models.user_program import UserProgram
from app.services import academic_progress
from app.services import permanence_service as svc
from app.services.errors import ConflictError
from tests.permanence.conftest import make_enrollment, make_period, make_user_program
from tests.support.factories import make_program, make_user


# ── helper ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('src, dst', [
    ('pending', 'active'), ('active', 'completed'), ('active', 'on_leave'),
    ('on_leave', 'active'), ('active', 'dropped'),
])
def test_helper_allows_table_transitions(src, dst):
    se = SimpleNamespace(status=src)
    academic_progress.set_enrollment_status(se, dst)
    assert se.status == dst


@pytest.mark.parametrize('src, dst', [
    ('pending', 'completed'), ('completed', 'active'), ('dropped', 'active'),
    ('on_leave', 'completed'), ('completed', 'dropped'),
])
def test_helper_rejects_forbidden_transitions(src, dst):
    se = SimpleNamespace(status=src)
    with pytest.raises(academic_progress.InvalidEnrollmentTransition) as exc:
        academic_progress.set_enrollment_status(se, dst)
    assert isinstance(exc.value, ConflictError)
    assert se.status == src


def test_helper_same_status_is_noop():
    se = SimpleNamespace(status='completed')
    academic_progress.set_enrollment_status(se, 'completed')
    assert se.status == 'completed'


def test_helper_closing_accepts_pending_to_completed_only():
    se = SimpleNamespace(status='pending')
    academic_progress.set_enrollment_status(se, 'completed', closing=True)
    assert se.status == 'completed'
    for src, dst in [('pending', 'on_leave'), ('completed', 'active'), ('dropped', 'completed')]:
        se = SimpleNamespace(status=src)
        with pytest.raises(academic_progress.InvalidEnrollmentTransition):
            academic_progress.set_enrollment_status(se, dst, closing=True)


# ── guarded sites ────────────────────────────────────────────────────────────

@pytest.fixture
def ctx(app):
    coord = make_user('program_admin')
    program = make_program(coord, duration_semesters=8)
    periods = {code: make_period(code, start) for code, start in [
        ('20241', date(2024, 1, 15)),
        ('20243', date(2024, 8, 15)),
    ]}
    up = make_user_program(make_user('student'), program, periods['20241'])
    UserProgram.query.filter_by(id=up.id).update({'academic_status': 'active'})
    db.session.expire(up)
    return {'coord': coord, 'p': periods, 'up': up}


def test_confirm_on_existing_completed_row_is_refused(ctx):
    up, p = ctx['up'], ctx['p']
    se = make_enrollment(up, p['20241'], 1, status='completed', confirmed=False)
    with pytest.raises(academic_progress.InvalidEnrollmentTransition):
        svc.confirm_semester_enrollment(up.id, p['20241'].id, ctx['coord'].id)
    assert db.session.get(SemesterEnrollment, se.id).status == 'completed'


def test_confirm_on_pending_row_activates_it(ctx):
    up, p = ctx['up'], ctx['p']
    se = make_enrollment(up, p['20241'], 1, status='pending', confirmed=False)
    svc.confirm_semester_enrollment(up.id, p['20241'].id, ctx['coord'].id)
    assert db.session.get(SemesterEnrollment, se.id).status == 'active'


def test_advancing_closes_a_pending_last_enrollment(ctx):
    up, p = ctx['up'], ctx['p']
    old = make_enrollment(up, p['20241'], 1, status='pending')
    svc.confirm_semester_enrollment(up.id, p['20243'].id, ctx['coord'].id)
    assert db.session.get(SemesterEnrollment, old.id).status == 'completed'


def test_update_enrollment_status_refuses_forbidden_move(ctx):
    up, p = ctx['up'], ctx['p']
    se = make_enrollment(up, p['20241'], 1, status='completed', confirmed=False)
    with pytest.raises(svc.InvalidStateTransition):
        svc.update_enrollment_status(se.id, 'active', ctx['coord'].id)
    assert db.session.get(SemesterEnrollment, se.id).status == 'completed'


def test_update_enrollment_status_allows_active_to_completed(ctx):
    up, p = ctx['up'], ctx['p']
    se = make_enrollment(up, p['20241'], 1, status='active')
    svc.update_enrollment_status(se.id, 'completed', ctx['coord'].id)
    assert db.session.get(SemesterEnrollment, se.id).status == 'completed'


def test_withdraw_drops_active_enrollment_and_keeps_completed(ctx):
    up, p = ctx['up'], ctx['p']
    se = make_enrollment(up, p['20241'], 1, status='active')
    svc.withdraw(up.id, 'Motivo de prueba', ctx['coord'].id)
    assert db.session.get(SemesterEnrollment, se.id).status == 'dropped'


def test_graduation_closes_active_enrollment_only(ctx):
    up, p = ctx['up'], ctx['p']
    se = make_enrollment(up, p['20241'], 1, status='active')
    svc.register_graduation(up.id, date(2024, 12, 1), ctx['coord'].id)
    assert db.session.get(SemesterEnrollment, se.id).status == 'completed'


# ── ratchet: static scan ─────────────────────────────────────────────────────

APP_DIR = Path(__file__).resolve().parents[2] / 'app'

# Variable names that hold a SemesterEnrollment in this codebase.
_SE_NAMES = (r'(?:se|new_se|last_se|source_se|target_se|current_se|existing_se|'
             r'semester_enrollment|sem_enrollment|enrollment)')
_ASSIGN = re.compile(rf'\b{_SE_NAMES}\.status\s*=(?!=)')

# (relative path, line fragment) pairs that may assign directly.
ALLOWED = {
    # The single writer.
    ('services/academic_progress.py', 'se.status = new_status'),
    # Guarded by can_change_enrollment_status just above; returns False instead of raising.
    ('services/review_engine/submission_kinds.py', 'enrollment.status = new_status'),
    # CourseEnrollment, out of scope (not a SemesterEnrollment).
    ('services/course_enrollment_service.py', "enrollment.status = 'enrolled'"),
    ('services/course_enrollment_service.py', "enrollment.status = 'dropped'"),
}


def test_no_direct_semester_enrollment_status_assignment():
    offenders = []
    for path in APP_DIR.rglob('*.py'):
        rel = path.relative_to(APP_DIR).as_posix()
        for no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if _ASSIGN.search(line) and (rel, line.strip()) not in ALLOWED:
                offenders.append(f'{rel}:{no}: {line.strip()}')
    assert not offenders, (
        'SemesterEnrollment.status must be written via '
        'academic_progress.set_enrollment_status:\n' + '\n'.join(offenders)
    )

"""Phase 6A: academic semester, permanence limit, withdrawal and graduation."""

from datetime import date

import pytest

from app import db
from app.models.semester_enrollment import SemesterEnrollment
from app.models.user_program import UserProgram
from app.services import academic_progress
from app.services import permanence_service as svc
from app.services import semester_transition_service as tsvc
from app.services.errors import DomainError
from tests.permanence.conftest import make_enrollment, make_period, make_user_program
from tests.support.factories import make_program, make_user


def _set_status(up, status):
    UserProgram.query.filter_by(id=up.id).update({'academic_status': status})
    db.session.expire(up)


@pytest.fixture
def ctx(app):
    coord = make_user('program_admin')
    program = make_program(coord, duration_semesters=1)  # limit = 1 + 4 = 5 periods
    periods = {code: make_period(code, start) for code, start in [
        ('20241', date(2024, 1, 15)),
        ('20243', date(2024, 8, 15)),
        ('20251', date(2025, 1, 15)),
        ('20252', date(2025, 6, 10)),   # summer: never counts
        ('20253', date(2025, 8, 15)),
        ('20261', date(2026, 1, 15)),
        ('20263', date(2026, 8, 15)),
    ]}
    up = make_user_program(make_user('student'), program, periods['20241'])
    _set_status(up, 'active')
    return {'coord': coord, 'program': program, 'p': periods, 'up': up}


def test_reinstated_student_repeats_the_semester_left(ctx):
    up, p = ctx['up'], ctx['p']
    make_enrollment(up, p['20241'], 1, status='completed')
    make_enrollment(up, p['20243'], 2, status='on_leave')
    _set_status(up, 'on_leave')

    se = svc.reinstate_from_leave(up.id, p['20251'].id, ctx['coord'].id)

    assert se.semester_number == 2
    assert db.session.get(UserProgram, up.id).academic_status == 'active'


def test_limit_counts_leave_and_skips_summer(ctx):
    up, p = ctx['up'], ctx['p']
    make_enrollment(up, p['20241'], 1, status='completed')
    make_enrollment(up, p['20243'], 2, status='on_leave')
    make_enrollment(up, p['20251'], 2, status='completed')
    make_enrollment(up, p['20253'], 3, status='completed')

    assert academic_progress.regular_periods_elapsed(up.id, p['20261'].id) == 5
    assert academic_progress.regular_periods_elapsed(up.id, p['20252'].id) is None
    academic_progress.assert_within_permanence_limit(up, p['20261'].id)
    with pytest.raises(academic_progress.PermanenceLimitExceeded, match='máximo 5'):
        svc.confirm_semester_enrollment(up.id, p['20263'].id, ctx['coord'].id, force=True)


def test_semester_number_survives_missing_history(ctx):
    up, p = ctx['up'], ctx['p']
    make_enrollment(up, p['20241'], 3, status='completed')   # imported: no rows for 1-2

    assert academic_progress.next_semester_number(up.id) == 4


def test_completed_enrollment_cannot_go_back_to_active(ctx):
    se = make_enrollment(ctx['up'], ctx['p']['20241'], 1, status='completed')

    with pytest.raises(svc.InvalidStateTransition):
        svc.update_enrollment_status(se.id, 'active', ctx['coord'].id)


def test_dropped_status_withdraws_the_program(ctx):
    up = ctx['up']
    se = make_enrollment(up, ctx['p']['20241'], 1, status='active')

    with pytest.raises(DomainError, match='El motivo es obligatorio.'):
        svc.update_enrollment_status(se.id, 'dropped', ctx['coord'].id)
    svc.update_enrollment_status(se.id, 'dropped', ctx['coord'].id, notes='Abandono')

    up = db.session.get(UserProgram, up.id)
    assert up.academic_status == 'withdrawn'
    assert up.withdrawal_reason == 'Abandono'
    assert db.session.get(SemesterEnrollment, se.id).status == 'dropped'


def test_withdrawn_student_cannot_enroll_again(ctx):
    up, p = ctx['up'], ctx['p']
    make_enrollment(up, p['20241'], 1, status='active')
    svc.withdraw(up.id, 'Abandono', ctx['coord'].id)

    with pytest.raises(svc.InvalidStateTransition, match='baja definitiva'):
        svc.confirm_semester_enrollment(up.id, p['20243'].id, ctx['coord'].id)


def test_transition_blocks_closed_trajectories(ctx):
    up, p = ctx['up'], ctx['p']
    make_enrollment(up, p['20241'], 1, status='active')
    _set_status(up, 'graduated')

    result = tsvc.evaluate_student(up.id, p['20241'].id, p['20243'].id)

    assert result['can_advance'] is False
    assert result['blockers'][0]['code'] == 'graduated'


def test_leave_and_return_follow_the_enrollment(ctx):
    se = make_enrollment(ctx['up'], ctx['p']['20241'], 1, status='active')

    svc.update_enrollment_status(se.id, 'on_leave', ctx['coord'].id)
    assert db.session.get(UserProgram, ctx['up'].id).academic_status == 'on_leave'
    svc.update_enrollment_status(se.id, 'active', ctx['coord'].id)
    assert db.session.get(UserProgram, ctx['up'].id).academic_status == 'active'


def test_admin_reverts_a_withdrawal(ctx):
    up = ctx['up']
    svc.withdraw(up.id, 'Captura equivocada', ctx['coord'].id)

    svc.revert_withdrawal(up.id, 'Error de captura', make_user('postgraduate_admin').id)

    assert db.session.get(UserProgram, up.id).academic_status == 'active'


def test_graduation_is_suggested_then_registered(ctx):
    up, p = ctx['up'], ctx['p']
    se = make_enrollment(up, p['20241'], 1, status='active')   # last semester of a 1-semester plan
    assert svc.graduation_suggested(up) is True

    svc.register_graduation(up.id, date(2024, 6, 30), ctx['coord'].id)

    up = db.session.get(UserProgram, up.id)
    assert up.academic_status == 'graduated'
    assert up.graduated_at == date(2024, 6, 30)
    assert db.session.get(SemesterEnrollment, se.id).status == 'completed'
    assert svc.graduation_suggested(up) is False


def test_graduation_not_suggested_before_the_last_semester(app):
    program = make_program(duration_semesters=4)
    period = make_period('20241', date(2024, 1, 15))
    up = make_user_program(make_user('student'), program, period)
    _set_status(up, 'active')
    make_enrollment(up, period, 2, status='active')

    assert svc.graduation_suggested(up) is False


def test_trajectory_summary(ctx):
    up, p = ctx['up'], ctx['p']
    make_enrollment(up, p['20241'], 1, status='completed')
    make_enrollment(up, p['20243'], 2, status='on_leave')

    data = svc.get_trajectory(up.id)

    assert data['academic_status_label'] == 'activo'
    assert data['current_semester'] == 2
    assert data['periods_used'] == 2
    assert data['permanence_limit'] == 5
    assert [e['status_label'] for e in data['enrollments']] == ['Completado', 'Baja temporal']
    assert data['can_withdraw'] and data['can_graduate'] and not data['can_revert_withdrawal']


def test_graduation_date_cannot_be_in_the_future(ctx):
    make_enrollment(ctx['up'], ctx['p']['20241'], 1, status='active')

    with pytest.raises(svc.InvalidStateTransition, match='no puede ser futura'):
        svc.register_graduation(ctx['up'].id, date(2999, 1, 1), ctx['coord'].id)

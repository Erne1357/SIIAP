"""Unit tests: app/services/admission_status_service.py (transition map, period distance)."""

from datetime import date

import pytest

from app import db
from app.models.academic_period import AcademicPeriod
from app.services import admission_status_service as svc
from app.services.admission_status_service import InvalidAdmissionTransition
from tests.support.factories import enroll, make_program, make_user


# ── transition map ───────────────────────────────────────────────────────────

def test_every_status_has_an_entry_in_the_map():
    assert set(svc.ALLOWED_TRANSITIONS) == svc.ALL_STATUSES


def test_map_only_targets_known_statuses():
    for targets in svc.ALLOWED_TRANSITIONS.values():
        assert targets <= svc.ALL_STATUSES


def test_enrolled_is_terminal():
    for to in svc.ALL_STATUSES:
        assert not svc.can_transition('enrolled', to)
        assert not svc.can_transition('enrolled', to, override=True)


@pytest.mark.parametrize('from_status', sorted(svc.ALL_STATUSES - {'enrolled'}))
def test_forced_reset_reaches_in_progress_from_every_non_terminal_status(from_status):
    assert svc.can_transition(from_status, 'in_progress')


def test_rejected_never_expires():
    assert not svc.can_transition('rejected', 'expired')


@pytest.mark.parametrize('from_status', sorted(svc.EXPIRABLE_STATUSES))
def test_expirable_statuses_can_expire(from_status):
    assert svc.can_transition(from_status, 'expired')


def test_deferred_comes_back_accepted():
    assert svc.can_transition('deferred', 'accepted')


@pytest.mark.parametrize('from_status, to_status', [
    ('in_progress', 'accepted'),        # no decision without interview
    ('in_progress', 'deliberation'),
    ('in_progress', 'enrolled'),
    ('rejected', 'accepted'),
    ('expired', 'accepted'),
    ('deferred', 'enrolled'),
    ('accepted', 'rejected'),
])
def test_disallowed_moves(from_status, to_status):
    assert not svc.can_transition(from_status, to_status)


def test_unknown_target_is_rejected():
    assert not svc.can_transition('in_progress', 'graduated')
    assert not svc.can_transition('in_progress', 'graduated', override=True)


@pytest.mark.parametrize('from_status', sorted(svc.ALL_STATUSES - {'enrolled'}))
def test_override_reaches_enrolled_from_any_non_terminal_status(from_status):
    assert svc.can_transition(from_status, 'enrolled', override=True)


def test_override_only_widens_override_targets():
    assert not svc.can_transition('rejected', 'accepted', override=True)


# ── transition() ─────────────────────────────────────────────────────────────

def test_transition_writes_and_returns_previous(app):
    up = enroll(make_user(), make_program(), 'interview_completed')
    assert svc.transition(up, 'deliberation') == 'interview_completed'
    assert up.admission_status == 'deliberation'


def test_transition_refuses_and_leaves_status_untouched(app):
    up = enroll(make_user(), make_program(), 'enrolled')
    with pytest.raises(InvalidAdmissionTransition) as e:
        svc.transition(up, 'in_progress')
    assert up.admission_status == 'enrolled'
    assert e.value.from_status == 'enrolled' and e.value.to_status == 'in_progress'
    assert '"inscrito"' in str(e.value) and '"en proceso"' in str(e.value)


def test_lock_user_program_returns_the_row(app):
    user, program = make_user(), make_program()
    up = enroll(user, program)
    assert svc.lock_user_program(user.id, program.id).id == up.id
    assert svc.lock_user_program(user.id, program.id + 999) is None


# ── period distance ──────────────────────────────────────────────────────────

def _period(code, start):
    p = AcademicPeriod(
        code=code, name=f'Periodo {code}', start_date=start,
        end_date=date(start.year, start.month, 28),
        admission_start_date=start, admission_end_date=start,
        is_active=False, status='upcoming',
    )
    db.session.add(p)
    db.session.flush()
    return p


@pytest.fixture
def periods(app):
    # Created out of order on purpose: ordering must come from start_date.
    p20263 = _period('20263', date(2026, 8, 1))
    p20261 = _period('20261', date(2026, 1, 15))
    p20262 = _period('20262', date(2026, 6, 15))   # summer
    p20271 = _period('20271', date(2027, 1, 15))
    p20272 = _period('20272', date(2027, 6, 15))   # summer
    p20273 = _period('20273', date(2027, 8, 1))
    return {p.code: p for p in (p20261, p20262, p20263, p20271, p20272, p20273)}


def test_is_summer_period(periods):
    assert svc.is_summer_period(periods['20262'])
    assert not svc.is_summer_period(periods['20263'])


def test_regular_period_ids_skip_summer_and_follow_start_date(periods):
    assert svc.regular_period_ids() == [
        periods['20261'].id, periods['20263'].id, periods['20271'].id, periods['20273'].id,
    ]


def test_distance_ignores_summer(periods):
    # 2026-3 -> 2027-1 -> 2027-3: two regular periods, summer 2027 not counted.
    assert svc.regular_periods_between(periods['20263'].id, periods['20273'].id) == 2
    assert svc.regular_periods_between(periods['20261'].id, periods['20263'].id) == 1


def test_distance_to_a_summer_target_is_none(periods):
    assert svc.regular_periods_between(periods['20263'].id, periods['20272'].id) is None


def test_summer_start_is_anchored_to_the_next_regular_period(periods):
    # Admitted in summer 2026 -> measured from 2026-3.
    assert svc.regular_periods_between(periods['20262'].id, periods['20263'].id) == 0
    assert svc.regular_periods_between(periods['20262'].id, periods['20273'].id) == 2


def test_summer_start_without_a_later_regular_period_is_none(periods):
    assert svc.regular_periods_between(periods['20272'].id, periods['20273'].id) == 0
    late = _period('20282', date(2028, 6, 15))
    assert svc.regular_periods_between(late.id, periods['20273'].id) is None


def test_distance_with_missing_period_is_none(periods):
    assert svc.regular_periods_between(None, periods['20263'].id) is None
    assert svc.regular_periods_between(periods['20263'].id, 999999) is None


def test_periods_closed_since_counts_regular_closed_only(periods):
    # As of 2027-07-01: 2027-1 closed (regular), 2027-2 closed (summer, ignored),
    # 2027-3 not closed yet.
    assert svc.regular_periods_closed_since(periods['20263'], date(2027, 7, 1)) == 1
    assert svc.regular_periods_closed_since(periods['20263'], date(2027, 9, 1)) == 2


def test_periods_closed_since_anchors_a_summer_period(periods):
    # Summer 2026 counts like 2026-3: same result as the regular case above.
    assert svc.regular_periods_closed_since(periods['20262'], date(2027, 9, 1)) == 2
    assert svc.regular_periods_closed_since(_period('20282', date(2028, 6, 15)), date(2029, 1, 1)) == 0

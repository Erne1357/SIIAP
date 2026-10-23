"""academic_status_service: the trajectory state machine of an enrolled student."""

from datetime import date

import pytest

from app import db
from app.models.user_history import UserHistory
from app.services import academic_status_service as svc
from app.services.errors import DomainError
from tests.support.factories import enroll, make_program, make_user


@pytest.fixture
def up(app):
    return enroll(make_user('student'), make_program(), admission_status='enrolled')


def _set(up, status):
    """Put `up` in `status` without going through the machine (test setup only)."""
    type(up).query.filter_by(id=up.id).update({'academic_status': status})
    db.session.expire(up)


ALLOWED = [
    (None, 'active'),
    ('active', 'on_leave'),
    ('active', 'withdrawn'),
    ('active', 'graduated'),
    ('on_leave', 'active'),
    ('on_leave', 'withdrawn'),
    ('graduated', 'titled'),
    ('titled', 'graduated'),
]
FORBIDDEN = [
    (None, 'graduated'),
    (None, 'withdrawn'),
    ('on_leave', 'graduated'),
    ('graduated', 'active'),
    ('graduated', 'withdrawn'),
    ('withdrawn', 'on_leave'),
    ('withdrawn', 'graduated'),
    ('active', 'titled'),
    ('on_leave', 'titled'),
    ('titled', 'active'),
    ('titled', 'withdrawn'),
]


@pytest.mark.parametrize('from_status,to_status', ALLOWED)
def test_allowed_moves(from_status, to_status):
    assert svc.can_transition(from_status, to_status)


@pytest.mark.parametrize('from_status,to_status', FORBIDDEN)
def test_forbidden_moves(from_status, to_status):
    assert not svc.can_transition(from_status, to_status)


def test_transition_raises_outside_the_map(app):
    applicant = enroll(make_user('applicant'), make_program())
    with pytest.raises(svc.InvalidAcademicTransition) as exc:
        svc.transition(applicant, 'graduated', actor_id=None, on_date=date(2026, 7, 1))
    assert 'sin inscripción' in str(exc.value)


def test_withdraw_requires_reason_and_stamps_it(up):
    _set(up, 'active')
    with pytest.raises(DomainError, match='El motivo es obligatorio.'):
        svc.transition(up, 'withdrawn', actor_id=None, reason='   ')

    previous = svc.transition(up, 'withdrawn', actor_id=None, reason='Abandono')

    assert previous == 'active'
    assert up.academic_status == 'withdrawn'
    assert up.withdrawal_reason == 'Abandono'
    assert up.withdrawn_at is not None
    assert up.academic_status_changed_at is not None


def test_revert_needs_admin_flag_and_reason(up):
    _set(up, 'withdrawn')
    with pytest.raises(svc.InvalidAcademicTransition):
        svc.transition(up, 'active', actor_id=None, reason='Error de captura')
    with pytest.raises(DomainError, match='El motivo es obligatorio.'):
        svc.transition(up, 'active', actor_id=None, allow_revert=True)

    svc.transition(up, 'active', actor_id=None, reason='Error de captura', allow_revert=True)

    assert up.academic_status == 'active'


def test_graduation_requires_date(up):
    _set(up, 'active')
    with pytest.raises(DomainError, match='La fecha de egreso es obligatoria.'):
        svc.transition(up, 'graduated', actor_id=None)

    svc.transition(up, 'graduated', actor_id=None, on_date=date(2026, 7, 1))

    assert up.graduated_at == date(2026, 7, 1)


def test_transition_logs_history_with_user_program(up):
    admin = make_user('postgraduate_admin')
    svc.transition(up, 'active', actor_id=admin.id)
    db.session.flush()

    entry = UserHistory.query.filter_by(action='academic_status_changed').one()
    assert entry.user_id == up.user_id
    assert entry.admin_id == admin.id
    assert entry.user_program_id == up.id
    assert '"to": "active"' in entry.details


def test_enrolled_row_without_status_counts_as_active(up):
    """A row the previous color enrolled during the blue-green switch has NULL."""
    svc.transition(up, 'withdrawn', actor_id=None, reason='Abandono')

    assert up.academic_status == 'withdrawn'


def test_applicant_without_status_cannot_be_withdrawn(app):
    applicant = enroll(make_user('applicant'), make_program())

    with pytest.raises(svc.InvalidAcademicTransition):
        svc.transition(applicant, 'withdrawn', actor_id=None, reason='x')


def test_titling_requires_exam_date_and_stamps_it(up):
    _set(up, 'graduated')
    with pytest.raises(DomainError, match='La fecha del examen de grado es obligatoria.'):
        svc.transition(up, 'titled', actor_id=None)

    svc.transition(up, 'titled', actor_id=None, on_date=date(2026, 9, 1))

    assert up.academic_status == 'titled'
    assert up.titled_at == date(2026, 9, 1)
    assert svc.STATUS_LABELS_ES['titled'] == 'titulado'


def test_titled_revert_needs_admin_flag_and_reason_and_keeps_graduation(up):
    _set(up, 'graduated')
    up.graduated_at = date(2026, 6, 1)
    svc.transition(up, 'titled', actor_id=None, on_date=date(2026, 9, 1))

    with pytest.raises(svc.InvalidAcademicTransition):
        svc.transition(up, 'graduated', actor_id=None, reason='Error')
    with pytest.raises(DomainError, match='El motivo es obligatorio.'):
        svc.transition(up, 'graduated', actor_id=None, allow_revert=True)

    svc.transition(up, 'graduated', actor_id=None, reason='Error', allow_revert=True)

    assert up.academic_status == 'graduated'
    assert up.titled_at is None
    assert up.graduated_at == date(2026, 6, 1)

"""User.current_user_program(): the single place that picks one UserProgram."""

from datetime import timedelta

from app import db
from app.models.user_program import UserProgram
from app.utils.datetime_utils import now_local
from tests.support.factories import enroll, make_program, make_user


def _set(up, **cols):
    UserProgram.query.filter_by(id=up.id).update(cols)
    db.session.commit()
    db.session.refresh(up)


def test_no_programs_returns_none(app):
    user = make_user('applicant')
    db.session.commit()
    assert user.current_user_program() is None


def test_graduated_master_and_active_doctorate_picks_doctorate(app):
    user = make_user('applicant')
    master, doctorate = make_program(), make_program()
    old = enroll(user, master, 'enrolled')
    new = enroll(user, doctorate, 'in_progress')
    _set(old, academic_status='graduated', enrollment_date=now_local() - timedelta(days=900))
    _set(new, enrollment_date=now_local())
    assert user.current_user_program().id == new.id


def test_only_enrolled_active_returns_it(app):
    user = make_user('student')
    up = enroll(user, make_program(), 'enrolled')
    _set(up, academic_status='active')
    assert user.current_user_program().id == up.id


def test_enrolled_with_null_academic_status_is_eligible(app):
    user = make_user('student')
    graduated = enroll(user, make_program(), 'enrolled')
    legacy = enroll(user, make_program(), 'enrolled')
    _set(graduated, academic_status='graduated')
    assert user.current_user_program().id == legacy.id


def test_active_beats_null_among_enrolled(app):
    user = make_user('student')
    null_up = enroll(user, make_program(), 'enrolled')
    active = enroll(user, make_program(), 'enrolled')
    _set(null_up, enrollment_date=now_local())
    _set(active, academic_status='on_leave', enrollment_date=now_local() - timedelta(days=100))
    assert user.current_user_program().id == active.id


def test_admission_in_flight_beats_enrolled(app):
    user = make_user('student')
    enrolled = enroll(user, make_program(), 'enrolled')
    flight = enroll(user, make_program(), 'accepted')
    _set(enrolled, academic_status='active', enrollment_date=now_local())
    _set(flight, enrollment_date=now_local() - timedelta(days=50))
    assert user.current_user_program().id == flight.id


def test_most_recent_in_flight_wins(app):
    user = make_user('applicant')
    a = enroll(user, make_program(), 'in_progress')
    b = enroll(user, make_program(), 'deferred')
    _set(a, enrollment_date=now_local() - timedelta(days=10))
    _set(b, enrollment_date=now_local())
    assert user.current_user_program().id == b.id


def test_fallback_is_most_recent_of_any(app):
    user = make_user('applicant')
    a = enroll(user, make_program(), 'rejected')
    b = enroll(user, make_program(), 'expired')
    _set(a, enrollment_date=now_local() - timedelta(days=10))
    _set(b, enrollment_date=now_local())
    assert user.current_user_program().id == b.id

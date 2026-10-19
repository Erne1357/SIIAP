# tests/transition/test_applicant_rules.py
"""
Applicant rules of the semester transition (execute + preview must agree):
rejected never expires, only EXPIRABLE statuses expire at delta 2, summer
periods do not count, only `deferred` applicants are reactivated (as
`accepted`), and a summer target leaves applicants untouched.
"""
from datetime import date, timedelta

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.enrollment_deferral import EnrollmentDeferral
from app.models.user import User
from app.models.user_program import UserProgram
from app.services import semester_transition_service as tsvc


def _applicant(roles, program, period, status, tag):
    u = User(
        first_name='Asp', last_name=tag, mother_last_name='',
        username=f'asp_rules_{tag}', password='Test1234!',
        email=f'asprules{tag}@t.local', is_internal=True,
        role_id=roles['applicant'].id, must_change_password=False,
    )
    db.session.add(u)
    db.session.flush()
    up = UserProgram(
        user_id=u.id, program_id=program.id,
        admission_status=status, admission_period_id=period.id,
    )
    db.session.add(up)
    db.session.flush()
    return up


def _period(code, start, end):
    sd = date.fromisoformat(start)
    p = AcademicPeriod(
        code=code, name=f'Period {code}', start_date=sd,
        end_date=date.fromisoformat(end),
        admission_start_date=sd - timedelta(days=60),
        admission_end_date=sd - timedelta(days=10),
        is_active=False, status='upcoming',
    )
    db.session.add(p)
    db.session.flush()
    return p


def _run(program, periods, admin, source='20263', target='20271'):
    return tsvc.execute_program_transition(
        program.id, periods[source].id, periods[target].id,
        coordinator_id=admin.id,
    )


def _preview_ids(program, periods, key, source='20263', target='20271'):
    out = tsvc.preview_program(program.id, periods[source].id, periods[target].id)
    return [r['user_program']['id'] for r in out[key]]


def _fresh(up):
    db.session.expire_all()
    return UserProgram.query.get(up.id)


def test_rejected_at_delta_2_is_never_expired(app, periods, program, roles, postgrad_admin):
    up = _applicant(roles, program, periods['20253'], 'rejected', 'rej')
    db.session.commit()

    assert up.id not in _preview_ids(program, periods, 'admission_expire')
    stats = _run(program, periods, postgrad_admin)

    assert stats['admission_expired'] == 0
    assert _fresh(up).admission_status == 'rejected'


def test_accepted_at_delta_2_expires(app, periods, program, roles, postgrad_admin):
    up = _applicant(roles, program, periods['20253'], 'accepted', 'acc')
    db.session.commit()

    assert up.id in _preview_ids(program, periods, 'admission_expire')
    stats = _run(program, periods, postgrad_admin)

    assert stats['admission_expired'] == 1
    assert _fresh(up).admission_status == 'expired'


def test_deferred_with_active_deferral_comes_back_accepted(app, periods, program, roles,
                                                           postgrad_admin):
    up = _applicant(roles, program, periods['20253'], 'deferred', 'def')
    d = EnrollmentDeferral(
        user_program_id=up.id, original_period_id=periods['20253'].id,
        deferred_to_period_id=periods['20271'].id, deferral_number=1,
        status='active', requested_by='applicant',
    )
    db.session.add(d)
    db.session.commit()

    assert up.id in _preview_ids(program, periods, 'deferred_reactivate')
    stats = _run(program, periods, postgrad_admin)

    assert stats['deferred_reactivated'] == 1
    re_up = _fresh(up)
    assert re_up.admission_status == 'accepted'
    assert re_up.admission_period_id == periods['20271'].id
    assert EnrollmentDeferral.query.get(d.id).status == 'used'


def test_deferred_without_deferral_is_left_alone(app, periods, program, roles, postgrad_admin):
    """Deferred applicants are handled only by the deferral flow."""
    up = _applicant(roles, program, periods['20253'], 'deferred', 'defnone')
    db.session.commit()

    assert up.id not in _preview_ids(program, periods, 'admission_expire')
    stats = _run(program, periods, postgrad_admin)

    assert stats['admission_expired'] == 0
    assert stats['deferred_reactivated'] == 0
    assert _fresh(up).admission_status == 'deferred'


def test_active_deferral_but_not_deferred_is_not_reactivated(app, periods, program, roles,
                                                             postgrad_admin):
    up = _applicant(roles, program, periods['20263'], 'accepted', 'stale')
    d = EnrollmentDeferral(
        user_program_id=up.id, original_period_id=periods['20263'].id,
        deferred_to_period_id=periods['20271'].id, deferral_number=1,
        status='active', requested_by='applicant',
    )
    db.session.add(d)
    db.session.commit()

    assert up.id not in _preview_ids(program, periods, 'deferred_reactivate')
    stats = _run(program, periods, postgrad_admin)

    assert stats['deferred_reactivated'] == 0
    assert EnrollmentDeferral.query.get(d.id).status == 'active'
    assert _fresh(up).admission_status == 'accepted'


def test_summer_period_is_not_counted(app, periods, program, roles, postgrad_admin):
    """Admission 2026-3, target 2027-3, summer 2027-2 in between: delta 2, not 3."""
    _period('20272', '2027-06-20', '2027-08-10')
    p3 = _period('20273', '2027-08-15', '2027-12-15')
    periods = {**periods, '20273': p3}
    up = _applicant(roles, program, periods['20263'], 'in_progress', 'sum')
    db.session.commit()

    assert up.id in _preview_ids(program, periods, 'admission_expire', target='20273')
    assert up.id not in _preview_ids(program, periods, 'admission_to_cleanup', target='20273')
    stats = _run(program, periods, postgrad_admin, target='20273')

    assert stats['admission_expired'] == 1
    assert _fresh(up).admission_status == 'expired'


def test_summer_target_leaves_applicants_untouched(app, periods, program, roles,
                                                   postgrad_admin):
    summer = _period('20272', '2027-06-20', '2027-08-10')
    periods = {**periods, '20272': summer}
    old = _applicant(roles, program, periods['20253'], 'in_progress', 'sold')
    recent = _applicant(roles, program, periods['20263'], 'in_progress', 'srec')
    db.session.commit()

    out = tsvc.preview_program(program.id, periods['20271'].id, summer.id)
    for key in ('admission_migrate', 'admission_expire', 'admission_to_cleanup'):
        assert not out[key]
    stats = tsvc.execute_program_transition(
        program.id, periods['20271'].id, summer.id, coordinator_id=postgrad_admin.id,
    )

    assert stats['admission_migrated'] == 0
    assert stats['admission_expired'] == 0
    assert _fresh(old).admission_status == 'in_progress'
    assert _fresh(old).admission_period_id == periods['20253'].id
    assert _fresh(recent).admission_period_id == periods['20263'].id

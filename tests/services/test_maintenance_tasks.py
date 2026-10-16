"""
Celery maintenance / event tasks, called through `.run` inside an app context.

Asserts on persisted effects (notifications, queue rows, flags), never on mocks
of the services under test.
"""

from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.email_queue import EmailQueue
from app.models.enrollment_deferral import EnrollmentDeferral
from app.models.notification import Notification
from app.models.program_admission_interest import ProgramAdmissionInterest
from app.models.semester_enrollment import SemesterEnrollment
from app.models.user_history import UserHistory
from app.models.user_program import UserProgram
from app.tasks import events as event_tasks
from app.tasks import maintenance as m
from app.utils.datetime_utils import now_local
from tests.support.factories import enroll, make_academic_period, make_program, make_user

TODAY = date(2026, 3, 10)


def _period(code, *, start, end, adm_start=None, adm_end=None, active=False):
    p = make_academic_period(code, is_active=active)
    p.start_date, p.end_date = start, end
    p.admission_start_date = adm_start or start - timedelta(days=90)
    p.admission_end_date = adm_end or start - timedelta(days=30)
    db.session.flush()
    return p


# ---------------------------------------------------------------- cleanup
class TestCleanupOldNotificationsTask:
    def test_marks_old_read_only(self, app):
        u = make_user('applicant')
        db.session.commit()
        from app.services.notification_service import NotificationService as NS
        with freeze_time('2026-01-01'):
            old_n = NS.create_notification(u.id, 't', 'a', 'b')
            keep_n = NS.create_notification(u.id, 't', 'a', 'b')
            old_n.is_read = True
            db.session.commit()
            old, keep = old_n.id, keep_n.id
        with freeze_time('2026-03-01'):
            db.session.expunge_all()
            assert m.cleanup_old_notifications.run() == {'marked_deleted': 1}
        assert Notification.query.get(old).is_deleted is True
        assert Notification.query.get(keep).is_deleted is False

    def test_custom_days(self, app):
        u = make_user('applicant')
        db.session.commit()
        from app.services.notification_service import NotificationService as NS
        with freeze_time('2026-03-01'):
            n = NS.create_notification(u.id, 't', 'a', 'b')
            n.is_read = True
            db.session.commit()
        with freeze_time('2026-03-05'):
            db.session.expunge_all()
            assert m.cleanup_old_notifications.run(days=2) == {'marked_deleted': 1}

    def test_empty_is_zero(self, app):
        assert m.cleanup_old_notifications.run() == {'marked_deleted': 0}


# ------------------------------------------------- admission period open
class TestNotifyAdmissionPeriodOpen:
    def _setup(self, with_interest=True, period_id='current'):
        coord = make_user('program_admin')
        prog = make_program(coord, name='Doctorado Z', slug='doc-z')
        user = make_user('applicant')
        p = make_academic_period('20261', is_active=True)
        p.admission_start_date = TODAY - timedelta(days=5)
        p.admission_end_date = TODAY + timedelta(days=20)
        db.session.flush()
        interest = None
        if with_interest:
            interest = ProgramAdmissionInterest(
                user_id=user.id, program_id=prog.id,
                period_id=p.id if period_id == 'current' else period_id)
            db.session.add(interest)
        db.session.commit()
        return user, prog, p, interest

    def test_notifies_marks_and_emails(self, app):
        user, prog, p, interest = self._setup()
        with freeze_time(f'{TODAY} 07:00:00'):
            r = m.notify_admission_period_open.run()
        assert r['notified'] == 1 and r['period'] == p.name
        n = Notification.query.filter_by(user_id=user.id, type='admission_period_open').one()
        assert n.priority == 'high' and prog.name in n.message
        assert n.action_url == f'/programs/{prog.slug}'
        assert EmailQueue.query.filter_by(user_id=user.id, notification_id=n.id).count() == 1
        assert ProgramAdmissionInterest.query.get(interest.id).notified_at is not None

    def test_message_uses_spanish_close_date(self, app):
        user, *_ = self._setup()
        with freeze_time(f'{TODAY} 07:00:00'):
            m.notify_admission_period_open.run()
        msg = Notification.query.filter_by(user_id=user.id).one().message
        assert 'de marzo de 2026' in msg or 'de abril de 2026' in msg

    def test_does_not_renotify(self, app):
        self._setup()
        with freeze_time(f'{TODAY} 07:00:00'):
            m.notify_admission_period_open.run()
            second = m.notify_admission_period_open.run()
        assert second == {'notified': 0, 'reason': 'no_pending_interest'}
        assert Notification.query.filter_by(type='admission_period_open').count() == 1

    def test_period_less_interest_is_served(self, app):
        user, *_ = self._setup(period_id=None)
        with freeze_time(f'{TODAY} 07:00:00'):
            assert m.notify_admission_period_open.run()['notified'] == 1

    def test_interest_for_other_period_waits(self, app):
        user, prog, p, _ = self._setup(with_interest=False)
        future = _period('20262', start=TODAY + timedelta(days=100),
                         end=TODAY + timedelta(days=250),
                         adm_start=TODAY + timedelta(days=40),
                         adm_end=TODAY + timedelta(days=80))
        db.session.add(ProgramAdmissionInterest(user_id=user.id, program_id=prog.id,
                                                period_id=future.id))
        db.session.commit()
        with freeze_time(f'{TODAY} 07:00:00'):
            assert m.notify_admission_period_open.run() == {
                'notified': 0, 'reason': 'no_pending_interest'}

    def test_no_open_period(self, app):
        self._setup()
        with freeze_time('2027-06-01 07:00:00'):
            assert m.notify_admission_period_open.run() == {
                'notified': 0, 'reason': 'no_open_period'}

    def test_window_boundaries_inclusive(self, app):
        user, *_ = self._setup()
        with freeze_time(f'{TODAY + timedelta(days=20)} 07:00:00'):
            assert m.notify_admission_period_open.run()['notified'] == 1

    def test_day_after_close_does_nothing(self, app):
        self._setup()
        with freeze_time(f'{TODAY + timedelta(days=21)} 07:00:00'):
            assert m.notify_admission_period_open.run()['reason'] == 'no_open_period'

    def test_email_failure_still_marks_and_notifies(self, app, monkeypatch):
        from app.services.email_service import EmailService

        def boom(*a, **k):
            raise RuntimeError('queue down')
        monkeypatch.setattr(EmailService, 'queue_email', staticmethod(boom))
        user, _, _, interest = self._setup()
        with freeze_time(f'{TODAY} 07:00:00'):
            assert m.notify_admission_period_open.run()['notified'] == 1
        assert Notification.query.filter_by(user_id=user.id).count() == 1

    def test_multiple_interested_users(self, app):
        user, prog, p, _ = self._setup()
        other = make_user('applicant')
        db.session.add(ProgramAdmissionInterest(user_id=other.id, program_id=prog.id,
                                                period_id=p.id))
        db.session.commit()
        with freeze_time(f'{TODAY} 07:00:00'):
            assert m.notify_admission_period_open.run()['notified'] == 2


# ------------------------------------------------ permanence pending docs
class TestNotifyPendingPermanenceDocs:
    def _student(self, prog, status='enrolled'):
        u = make_user('student')
        up = enroll(u, prog, status)
        return u, up

    def test_no_active_period(self, app):
        prog = make_program()
        self._student(prog)
        db.session.commit()
        assert m.notify_pending_permanence_docs.run() == {
            'notified': 0, 'reason': 'no_active_period'}

    def test_notifies_enrolled_without_confirmed_enrollment(self, app):
        prog = make_program()
        u, up = self._student(prog)
        period = make_academic_period('20261', is_active=True)
        db.session.commit()
        r = m.notify_pending_permanence_docs.run()
        assert r == {'notified': 1, 'period': period.name}
        n = Notification.query.filter_by(user_id=u.id).one()
        assert n.type == 'permanence_pending' and period.name in n.message

    def test_confirmed_students_skipped(self, app):
        prog = make_program()
        u, up = self._student(prog)
        period = make_academic_period('20261', is_active=True)
        se = SemesterEnrollment(user_program_id=up.id, academic_period_id=period.id,
                                semester_number=1)
        se.enrollment_confirmed = True
        db.session.add(se)
        db.session.commit()
        assert m.notify_pending_permanence_docs.run()['notified'] == 0

    def test_unconfirmed_enrollment_row_still_notified(self, app):
        prog = make_program()
        u, up = self._student(prog)
        period = make_academic_period('20261', is_active=True)
        db.session.add(SemesterEnrollment(user_program_id=up.id, academic_period_id=period.id,
                                          semester_number=1))
        db.session.commit()
        assert m.notify_pending_permanence_docs.run()['notified'] == 1

    @pytest.mark.parametrize('status', ['in_progress', 'accepted', 'deferred', 'rejected'])
    def test_non_enrolled_not_notified(self, app, status):
        prog = make_program()
        self._student(prog, status)
        make_academic_period('20261', is_active=True)
        db.session.commit()
        assert m.notify_pending_permanence_docs.run()['notified'] == 0

    def test_confirmation_in_other_period_does_not_count(self, app):
        prog = make_program()
        u, up = self._student(prog)
        old = make_academic_period('20253', is_active=False)
        make_academic_period('20261', is_active=True)
        se = SemesterEnrollment(user_program_id=up.id, academic_period_id=old.id,
                                semester_number=1)
        se.enrollment_confirmed = True
        db.session.add(se)
        db.session.commit()
        assert m.notify_pending_permanence_docs.run()['notified'] == 1


# ------------------------------------------------------ deferral expiry
class TestCheckDeferralExpirations:
    def _deferral(self, *, end, status='active', number=1, prev_used=0):
        prog = make_program()
        u = make_user('applicant')
        up = enroll(u, prog, 'deferred')
        orig = _period('20253', start=TODAY - timedelta(days=200), end=TODAY - timedelta(days=100))
        target = _period('20261', start=TODAY - timedelta(days=30), end=end)
        for i in range(prev_used):
            db.session.add(EnrollmentDeferral(
                user_program_id=up.id, original_period_id=orig.id,
                deferred_to_period_id=orig.id, deferral_number=i + 1, status='used'))
        d = EnrollmentDeferral(user_program_id=up.id, original_period_id=orig.id,
                               deferred_to_period_id=target.id, deferral_number=number,
                               status=status)
        db.session.add(d)
        db.session.commit()
        return u, up, d

    def test_expires_past_deferral_and_notifies(self, app):
        u, up, d = self._deferral(end=TODAY - timedelta(days=1))
        with freeze_time(f'{TODAY} 08:00:00'):
            r = m.check_deferral_expirations.run()
        assert r == {'expired': 1, 'notified': 0}
        assert EnrollmentDeferral.query.get(d.id).status == 'expired'
        assert Notification.query.filter_by(user_id=u.id, type='deferral_expired').count() == 1

    def test_process_stays_deferred_while_deferrals_remain(self, app):
        u, up, d = self._deferral(end=TODAY - timedelta(days=1))
        with freeze_time(f'{TODAY} 08:00:00'):
            m.check_deferral_expirations.run()
        assert UserProgram.query.get(up.id).admission_status == 'deferred'

    def test_process_expires_when_deferrals_exhausted(self, app):
        u, up, d = self._deferral(end=TODAY - timedelta(days=1), number=2, prev_used=1)
        with freeze_time(f'{TODAY} 08:00:00'):
            m.check_deferral_expirations.run()
        assert UserProgram.query.get(up.id).admission_status == 'expired'

    # Regression: flipping admission_status to 'expired' after exhausted deferrals wrote no history row.
    def test_exhausted_expiry_is_recorded_in_history(self, app):
        u, up, d = self._deferral(end=TODAY - timedelta(days=1), number=2, prev_used=1)
        with freeze_time(f'{TODAY} 08:00:00'):
            m.check_deferral_expirations.run()
        rows = UserHistory.query.filter_by(user_id=u.id, action='admission_expired').all()
        assert len(rows) == 1 and rows[0].admin_id is None

    def test_active_deferral_still_running_untouched(self, app):
        u, up, d = self._deferral(end=TODAY + timedelta(days=90))
        with freeze_time(f'{TODAY} 08:00:00'):
            r = m.check_deferral_expirations.run()
        assert r == {'expired': 0, 'notified': 0}
        assert EnrollmentDeferral.query.get(d.id).status == 'active'

    def test_warns_30_days_before_once(self, app):
        u, up, d = self._deferral(end=TODAY + timedelta(days=10))
        with freeze_time(f'{TODAY} 08:00:00'):
            first = m.check_deferral_expirations.run()
            second = m.check_deferral_expirations.run()
        assert first == {'expired': 0, 'notified': 1}
        assert second == {'expired': 0, 'notified': 0}
        assert Notification.query.filter_by(user_id=u.id, type='deferral_expiring').count() == 1
        assert EnrollmentDeferral.query.get(d.id).expiry_notified_at is not None

    def test_no_warning_if_more_than_30_days_left(self, app):
        self._deferral(end=TODAY + timedelta(days=31))
        with freeze_time(f'{TODAY} 08:00:00'):
            assert m.check_deferral_expirations.run()['notified'] == 0

    def test_warning_boundary_exactly_30_days(self, app):
        self._deferral(end=TODAY + timedelta(days=30))
        with freeze_time(f'{TODAY} 08:00:00'):
            assert m.check_deferral_expirations.run()['notified'] == 1

    @pytest.mark.parametrize('status', ['used', 'rejected', 'pending', 'expired'])
    def test_non_active_deferrals_ignored(self, app, status):
        self._deferral(end=TODAY - timedelta(days=1), status=status)
        with freeze_time(f'{TODAY} 08:00:00'):
            assert m.check_deferral_expirations.run() == {'expired': 0, 'notified': 0}

    def test_period_ending_today_is_not_yet_expired(self, app):
        u, up, d = self._deferral(end=TODAY)
        with freeze_time(f'{TODAY} 08:00:00'):
            assert m.check_deferral_expirations.run()['expired'] == 0


# ------------------------------------------------- deprecated cleanup task
class TestCleanupExpiredAdmissionFiles:
    # Regression: the task logged the unregistered action 'data_cleanup' (ValueError) and read current_user outside a request.
    def test_expires_stale_process(self, app):
        old = _period('20243', start=TODAY - timedelta(days=700), end=TODAY - timedelta(days=600),
                      adm_end=TODAY - timedelta(days=650))
        for code, off in (('20251', 500), ('20252', 400)):
            _period(code, start=TODAY - timedelta(days=off), end=TODAY - timedelta(days=off - 90),
                    adm_end=TODAY - timedelta(days=off + 10))
        prog = make_program()
        u = make_user('applicant')
        up = enroll(u, prog, 'in_progress')
        up.admission_period_id = old.id
        db.session.commit()
        with freeze_time(f'{TODAY} 03:00:00'):
            r = m.cleanup_expired_admission_files.run()
        assert r['expired_programs'] == 1
        assert UserProgram.query.get(up.id).admission_status == 'expired'
        rows = UserHistory.query.filter_by(user_id=u.id, action='data_cleanup').all()
        assert len(rows) == 1 and rows[0].admin_id is None


# ---------------------------------------------------------- event tasks
class TestEventReminderTasks:
    @pytest.mark.parametrize('task,window', [
        (event_tasks.dispatch_reminders_24h, '24h'),
        (event_tasks.dispatch_reminders_2h, '2h'),
    ])
    def test_delegates_with_right_window(self, app, monkeypatch, task, window):
        from app.services.event_reminder_service import EventReminderService
        seen = []
        monkeypatch.setattr(EventReminderService, 'dispatch_due_reminders',
                            staticmethod(lambda w: seen.append(w) or {'sent': 0, 'skipped': 0, 'failed': 0}))
        assert task.run() == {'sent': 0, 'skipped': 0, 'failed': 0}
        assert seen == [window]

    def test_no_events_is_noop(self, app):
        assert event_tasks.dispatch_reminders_24h.run() == {'sent': 0, 'skipped': 0, 'failed': 0}

    def test_failure_is_reraised_for_celery_retry(self, app, monkeypatch):
        from app.services.event_reminder_service import EventReminderService

        def boom(w):
            raise RuntimeError('db')
        monkeypatch.setattr(EventReminderService, 'dispatch_due_reminders', staticmethod(boom))
        with pytest.raises(RuntimeError):
            event_tasks.dispatch_reminders_2h.run()

    def test_task_names_registered_for_beat(self, app):
        assert event_tasks.dispatch_reminders_24h.name == 'app.tasks.events.dispatch_reminders_24h'
        assert m.purge_email_bodies.name == 'app.tasks.maintenance.purge_email_bodies'

"""NotificationService core behaviour and the bulk-notification Celery tasks."""

from datetime import timedelta

import pytest
from freezegun import freeze_time

from app import db
from app.models.email_queue import EmailQueue
from app.models.notification import Notification
from app.services.notification_service import NotificationService as NS
from app.tasks import notifications as tasks
from app.utils.datetime_utils import now_local
from tests.support.factories import enroll, make_program, make_user


@pytest.fixture
def user(app):
    u = make_user('applicant')
    db.session.commit()
    return u


def _n(user, type_='generic', **kw):
    n = NS.create_notification(user.id, type_, kw.pop('title', 't'), kw.pop('message', 'm'), **kw)
    db.session.commit()
    return n


class TestCreate:
    def test_defaults(self, user):
        n = _n(user)
        assert n.priority == 'medium' and n.is_read is False and n.is_deleted is False
        assert n.data == {} and n.action_url is None

    def test_persists_all_fields(self, user):
        n = _n(user, 'x', priority='high', data={'a': 1}, action_url='/u',
               expires_at=now_local() + timedelta(days=1))
        row = Notification.query.get(n.id)
        assert (row.type, row.priority, row.data, row.action_url) == ('x', 'high', {'a': 1}, '/u')
        assert row.expires_at is not None

    @pytest.mark.parametrize('type_', sorted(NS.ACTIONABLE_TYPES))
    def test_actionable_types_flagged(self, user, type_):
        assert _n(user, type_).is_actionable is True

    def test_non_actionable_type(self, user):
        assert _n(user, 'document_approved').is_actionable is False

    def test_socket_failure_does_not_lose_notification(self, user, monkeypatch):
        import app.extensions as ext

        def boom(*a, **k):
            raise RuntimeError('redis down')
        monkeypatch.setattr(ext.socketio, 'emit', boom)
        assert _n(user).id is not None

    def test_emits_to_user_room(self, user, monkeypatch):
        import app.extensions as ext
        sent = []
        monkeypatch.setattr(ext.socketio, 'emit',
                            lambda ev, payload, room=None, **k: sent.append((ev, room)))
        _n(user)
        assert ('notification:new', f'user:{user.id}') in sent


class TestReadAndDelete:
    def test_mark_as_read(self, user):
        n = _n(user)
        with freeze_time('2026-03-01 10:00:00'):
            NS.mark_as_read(n.id, user.id)
            assert n.is_read and n.read_at == now_local()

    def test_mark_as_read_other_users_notification_is_noop(self, user):
        other = make_user('applicant')
        n = _n(user)
        db.session.commit()
        assert NS.mark_as_read(n.id, other.id) is None
        assert Notification.query.get(n.id).is_read is False

    def test_mark_as_read_twice_keeps_first_timestamp(self, user):
        n = _n(user)
        with freeze_time('2026-03-01 10:00:00'):
            NS.mark_as_read(n.id, user.id)
            first = n.read_at
        with freeze_time('2026-03-02 10:00:00'):
            NS.mark_as_read(n.id, user.id)
        assert n.read_at == first

    def test_mark_all_as_read_counts_only_unread(self, user):
        a, b = _n(user), _n(user)
        NS.mark_as_read(a.id, user.id)
        assert NS.mark_all_as_read(user.id) == 1
        assert NS.get_unread_count(user.id) == 0

    def test_mark_all_scoped_to_user(self, user):
        other = make_user('applicant')
        _n(other)
        _n(user)
        NS.mark_all_as_read(user.id)
        assert NS.get_unread_count(other.id) == 1

    def test_mark_all_skips_deleted(self, user):
        n = _n(user)
        NS.delete_notification(n.id, user.id)
        assert NS.mark_all_as_read(user.id) == 0

    def test_delete_is_soft(self, user):
        n = _n(user)
        NS.delete_notification(n.id, user.id)
        assert Notification.query.get(n.id).is_deleted is True

    def test_delete_foreign_notification(self, user):
        other = make_user('applicant')
        n = _n(user)
        db.session.commit()
        assert NS.delete_notification(n.id, other.id) is None
        assert Notification.query.get(n.id).is_deleted is False

    def test_clear_read(self, user):
        a, b = _n(user), _n(user)
        NS.mark_as_read(a.id, user.id)
        assert NS.clear_read_notifications(user.id) == 1
        assert Notification.query.get(b.id).is_deleted is False


class TestListing:
    def test_newest_first_and_total(self, user):
        with freeze_time('2026-03-01'):
            old = _n(user, title='old')
        with freeze_time('2026-03-02'):
            new = _n(user, title='new')
        items, total = NS.get_user_notifications(user.id)
        assert total == 2 and [i.title for i in items] == ['new', 'old']

    def test_excludes_deleted(self, user):
        n = _n(user)
        NS.delete_notification(n.id, user.id)
        assert NS.get_user_notifications(user.id) == ([], 0)

    def test_unread_only(self, user):
        a, _ = _n(user), _n(user)
        NS.mark_as_read(a.id, user.id)
        items, total = NS.get_user_notifications(user.id, include_read=False)
        assert total == 1 and items[0].id != a.id

    def test_pagination(self, user):
        for i in range(5):
            _n(user, title=f'n{i}')
        items, total = NS.get_user_notifications(user.id, limit=2, offset=4)
        assert total == 5 and len(items) == 1

    def test_unread_count_ignores_other_users(self, user):
        _n(make_user('applicant'))
        db.session.commit()
        assert NS.get_unread_count(user.id) == 0


def _cleanup(days=30):
    # A fresh task session has no loaded rows; bulk UPDATE's in-Python criteria
    # evaluation would otherwise compare naive reloaded values with an aware cutoff.
    db.session.expunge_all()
    return NS.cleanup_old_notifications(days=days)


class TestCleanupOld:
    def test_only_old_read_notifications_removed(self, user):
        with freeze_time('2026-01-01'):
            old_read = _n(user).id
            old_unread = _n(user).id
            NS.mark_as_read(old_read, user.id)
        with freeze_time('2026-03-01'):
            new_read = _n(user).id
            NS.mark_as_read(new_read, user.id)
            assert _cleanup(days=30) == 1
        assert Notification.query.get(old_read).is_deleted is True
        assert Notification.query.get(old_unread).is_deleted is False
        assert Notification.query.get(new_read).is_deleted is False

    def test_boundary(self, user):
        # January/February: no DST shift between the two instants.
        with freeze_time('2026-01-10 12:00:00'):
            n = _n(user)
            NS.mark_as_read(n.id, user.id)
        with freeze_time('2026-02-09 11:59:00'):
            assert _cleanup(days=30) == 0
        with freeze_time('2026-02-09 12:01:00'):
            assert _cleanup(days=30) == 1

    def test_idempotent(self, user):
        with freeze_time('2026-01-01'):
            n = _n(user)
            NS.mark_as_read(n.id, user.id)
        with freeze_time('2026-03-01'):
            assert _cleanup() == 1
            assert _cleanup() == 0


class TestTypedNotifications:
    def test_password_reset_has_no_link_and_one_mail(self, user):
        n = NS.notify_password_reset(user.id, token_link='https://x/reset/SECRETTOK')
        db.session.commit()
        assert 'SECRETTOK' not in n.message and n.priority == 'critical'
        assert EmailQueue.query.filter_by(user_id=user.id).count() == 1

    def test_password_reset_without_link_sends_no_mail(self, user):
        NS.notify_password_reset(user.id, token_link=None)
        db.session.commit()
        assert EmailQueue.query.count() == 0

    def test_deliberation_accepted_queues_email_linked_to_notification(self, user):
        n = NS.notify_deliberation_accepted(user.id, 'Maestría X', 'http://x/dash')
        db.session.commit()
        mail = EmailQueue.query.one()
        assert mail.notification_id == n.id and 'Maestría X' in (mail.html_content + mail.subject)

    def test_rejection_partial_vs_full_types(self, user):
        a = NS.notify_deliberation_rejected(user.id, 'P', 'partial', 'n', 'http://x')
        b = NS.notify_deliberation_rejected(user.id, 'P', 'full', 'n', 'http://x')
        assert (a.type, b.type) == ('deliberation_corrections', 'deliberation_rejected')

    def test_email_failure_never_blocks_in_app_notification(self, user, monkeypatch):
        from app.services.email_service import EmailService

        def boom(*a, **k):
            raise RuntimeError('smtp')
        monkeypatch.setattr(EmailService, 'queue_email', staticmethod(boom))
        n = NS.notify_deliberation_accepted(user.id, 'P', 'http://x')
        assert n.id is not None

    def test_user_without_email_still_gets_in_app_notification(self, user):
        user.email = ''
        db.session.commit()
        n = NS.notify_deliberation_accepted(user.id, 'P', 'http://x')
        assert n.id is not None and EmailQueue.query.count() == 0

    def test_event_published_broadcast_does_not_email(self, user):
        assert NS.notify_event_published([user.id], 'Taller', 1) == 1
        assert EmailQueue.query.count() == 0


class TestBulkTasks:
    def test_send_bulk_creates_one_per_user(self, app):
        users = [make_user('applicant') for _ in range(3)]
        db.session.commit()
        r = tasks.send_bulk_notification.run([u.id for u in users], 'event_announcement', 'T', 'M')
        assert r == {'created': 3, 'errors': 0}
        assert Notification.query.filter_by(type='event_announcement').count() == 3

    def test_send_bulk_counts_errors_and_continues(self, app, monkeypatch):
        good = make_user('applicant')
        db.session.commit()
        real = NS.create_notification

        def flaky(user_id, *a, **k):
            if user_id == 424242:
                raise ValueError('bad')
            return real(user_id, *a, **k)
        monkeypatch.setattr(NS, 'create_notification', staticmethod(flaky))
        r = tasks.send_bulk_notification.run([424242, good.id], 't', 'T', 'M')
        assert r == {'created': 1, 'errors': 1}

    def test_send_bulk_with_email(self, app):
        u = make_user('applicant')
        db.session.commit()
        tasks.send_bulk_notification.run([u.id], 't', 'T', 'M', send_email=True,
                                         email_subject='S', email_html='<p>h</p>')
        assert EmailQueue.query.filter_by(user_id=u.id, subject='S').count() == 1

    def test_send_bulk_email_requires_subject_and_html(self, app):
        u = make_user('applicant')
        db.session.commit()
        tasks.send_bulk_notification.run([u.id], 't', 'T', 'M', send_email=True)
        assert EmailQueue.query.count() == 0

    def test_send_bulk_empty_list(self, app):
        assert tasks.send_bulk_notification.run([], 't', 'T', 'M') == {'created': 0, 'errors': 0}

    def test_service_send_bulk_dispatches_task(self, app, monkeypatch):
        seen = {}

        class T:
            id = 'abc'
        monkeypatch.setattr(tasks.send_bulk_notification, 'delay',
                            lambda **kw: seen.update(kw) or T())
        assert NS.send_bulk([1, 2], 't', 'T', 'M', priority='high') == 'abc'
        assert seen['user_ids'] == [1, 2] and seen['priority'] == 'high'

    def _capture_delegate(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(tasks.send_bulk_notification, 'delay',
                            lambda **kw: seen.update(kw))
        return seen

    def test_filter_all_only_active_users(self, app, monkeypatch):
        seen = self._capture_delegate(monkeypatch)
        a = make_user('applicant')
        make_user('applicant', is_active=False)
        db.session.commit()
        r = tasks.send_bulk_notification_by_filter.run('all', '', 't', 'T', 'M')
        assert r['user_ids_resolved'] == 1 and seen['user_ids'] == [a.id]

    def test_filter_program_distinct_users(self, app, monkeypatch):
        seen = self._capture_delegate(monkeypatch)
        prog = make_program()
        u = make_user('applicant')
        enroll(u, prog)
        db.session.commit()
        tasks.send_bulk_notification_by_filter.run('program', prog.id, 't', 'T', 'M')
        assert seen['user_ids'] == [u.id]

    def test_filter_unknown_type(self, app, monkeypatch):
        self._capture_delegate(monkeypatch)
        r = tasks.send_bulk_notification_by_filter.run('zzz', 'x', 't', 'T', 'M')
        assert 'error' in r

    # Regression: queried the nonexistent User.roles relationship (AttributeError).
    def test_filter_role(self, app, monkeypatch):
        seen = self._capture_delegate(monkeypatch)
        u = make_user('applicant')
        make_user('student')
        db.session.commit()
        tasks.send_bulk_notification_by_filter.run('role', 'applicant', 't', 'T', 'M')
        assert seen['user_ids'] == [u.id]

    # Regression: filtered the nonexistent UserProgram.status column instead of admission_status.
    def test_filter_process(self, app, monkeypatch):
        seen = self._capture_delegate(monkeypatch)
        prog = make_program()
        u = make_user('applicant')
        enroll(u, prog, 'accepted')
        db.session.commit()
        tasks.send_bulk_notification_by_filter.run('process', 'accepted', 't', 'T', 'M')
        assert seen['user_ids'] == [u.id]

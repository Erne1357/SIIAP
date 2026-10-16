"""
EmailService + the Celery tasks that drain EmailQueue.

Microsoft Graph and the Celery broker are faked (see tests/services/conftest.py),
so these assert on persisted EmailQueue rows and on what the fake "sent".
"""

from datetime import timedelta

import pytest
from freezegun import freeze_time

from app import db
from app.models.email_queue import EmailQueue
from app.services.email_service import BODY_RETENTION_HOURS, PURGED_BODY, EmailService
from app.tasks import maintenance, notifications
from app.utils.datetime_utils import now_local
from tests.support.factories import make_user


@pytest.fixture
def user(app):
    u = make_user('applicant')
    db.session.commit()
    return u


def _queue(user, subject='Hola', body='<p>cuerpo</p>'):
    item = EmailService.queue_email(user.id, subject, body)
    db.session.commit()
    return item


class TestQueueEmail:
    def test_creates_pending_row(self, user):
        item = _queue(user)
        row = EmailQueue.query.get(item.id)
        assert row.status == 'pending' and row.attempts == 0
        assert row.recipient_email == user.email
        assert row.subject == 'Hola' and row.html_content == '<p>cuerpo</p>'

    def test_schedules_async_send_with_countdown(self, user, celery_dispatch):
        item = _queue(user)
        assert len(celery_dispatch) == 1
        call = celery_dispatch[0]
        assert call['kwargs'] == {'args': [item.id], 'countdown': 1}

    def test_links_notification(self, user):
        item = EmailService.queue_email(user.id, 's', 'b', notification_id=None)
        assert item.notification_id is None

    def test_unknown_user_raises(self, app):
        with pytest.raises(ValueError):
            EmailService.queue_email(99999, 's', 'b')

    def test_user_without_email_raises(self, app):
        u = make_user('applicant')
        u.email = ''
        db.session.commit()
        with pytest.raises(ValueError):
            EmailService.queue_email(u.id, 's', 'b')
        assert EmailQueue.query.count() == 0

    def test_broker_failure_does_not_lose_the_row(self, user, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError('broker down')
        monkeypatch.setattr(notifications.send_email_async, 'apply_async', boom)
        item = _queue(user)
        assert EmailQueue.query.get(item.id).status == 'pending'

    def test_to_dict_never_exposes_body(self, user):
        item = _queue(user, body='<a href="https://x/reset/SECRET">')
        d = EmailQueue.query.get(item.id).to_dict()
        assert 'html_content' not in d
        assert 'SECRET' not in str(d)


class TestTrySend:
    def test_success_marks_sent(self, user, graph):
        item = _queue(user)
        assert EmailService._try_send_email(item) is True
        assert item.status == 'sent' and item.sent_at is not None
        assert graph.sent == [('Hola', (user.email,))]

    def test_200_also_counts_as_success(self, user, graph):
        graph.status_codes = [200]
        item = _queue(user)
        assert EmailService._try_send_email(item) is True

    def test_http_error_increments_attempts_and_schedules_retry(self, user, graph):
        graph.status_codes = [500]
        item = _queue(user)
        assert EmailService._try_send_email(item) is False
        assert item.status == 'pending' and item.attempts == 1
        assert '500' in item.error_message
        assert item.next_retry_at is not None

    def test_retry_is_five_minutes_out(self, user, graph):
        graph.status_codes = [500]
        item = _queue(user)
        with freeze_time('2026-03-01 10:00:00'):
            EmailService._try_send_email(item)
            delta = item.next_retry_at - now_local()
        assert timedelta(minutes=4, seconds=59) <= delta <= timedelta(minutes=5, seconds=1)

    def test_fails_definitively_at_max_attempts(self, user, graph):
        graph.status_codes = [500, 500, 500]
        item = _queue(user)
        for _ in range(3):
            EmailService._try_send_email(item)
        assert item.status == 'failed' and item.attempts == item.max_attempts == 3

    def test_exception_counts_as_failed_attempt(self, user, graph):
        graph.raise_exc = ConnectionError('net')
        item = _queue(user)
        assert EmailService._try_send_email(item) is False
        assert item.attempts == 1 and 'net' in item.error_message

    def test_no_token_is_not_an_attempt(self, user, graph):
        graph.token = None
        item = _queue(user)
        assert EmailService._try_send_email(item) is False
        assert item.attempts == 0 and item.status == 'pending'
        assert graph.sent == []

    def test_success_after_failure_clears_error(self, user, graph):
        graph.status_codes = [500, 202]
        item = _queue(user)
        EmailService._try_send_email(item)
        EmailService._try_send_email(item)
        assert item.status == 'sent' and item.error_message is None

    def test_purged_body_is_failed_not_mailed_empty(self, user, graph):
        item = _queue(user)
        item.html_content = PURGED_BODY
        assert EmailService._try_send_email(item) is False
        assert item.status == 'failed' and graph.sent == []
        assert 'purgado' in item.error_message


class TestProcessQueue:
    def test_sends_all_pending(self, user, graph):
        for i in range(3):
            _queue(user, subject=f's{i}')
        result = EmailService.process_queue()
        assert result == {'processed': 3, 'sent': 3, 'failed': 0}
        assert EmailQueue.query.filter_by(status='sent').count() == 3

    def test_skipped_without_microsoft_session(self, user, graph):
        _queue(user)
        graph.connected = False
        result = EmailService.process_queue()
        assert result['processed'] == 0 and 'error' in result
        assert EmailQueue.query.filter_by(status='pending').count() == 1

    def test_oldest_first_and_limit(self, user, graph):
        with freeze_time('2026-01-01'):
            _queue(user, subject='old')
        with freeze_time('2026-02-01'):
            _queue(user, subject='new')
        EmailService.process_queue(limit=1)
        assert [s for s, _ in graph.sent] == ['old']

    def test_mixed_results_counted(self, user, graph):
        graph.status_codes = [202, 500]
        _queue(user, 'a')
        _queue(user, 'b')
        result = EmailService.process_queue()
        assert result == {'processed': 2, 'sent': 1, 'failed': 1}

    def test_second_run_is_idempotent(self, user, graph):
        _queue(user)
        EmailService.process_queue()
        again = EmailService.process_queue()
        assert again['processed'] == 0
        assert len(graph.sent) == 1

    def test_failed_rows_are_not_picked_up(self, user, graph):
        item = _queue(user)
        item.status = 'failed'
        db.session.commit()
        assert EmailService.process_queue()['processed'] == 0

    def test_persists_results(self, user, graph):
        _queue(user)
        EmailService.process_queue()
        db.session.expire_all()
        assert EmailQueue.query.one().status == 'sent'

    # Regression: with no claim, a sweep during an in-flight send re-read the 'pending' row and mailed it twice.
    def test_two_workers_never_double_send(self, user, graph, monkeypatch):
        item = _queue(user)
        real = graph.graph_send_mail
        state = {'nested': False}

        def racing_send(*a, **k):
            # While worker A is mid-send (row still 'pending'), worker B sweeps.
            if not state['nested']:
                state['nested'] = True
                EmailService.process_queue()
            return real(*a, **k)

        monkeypatch.setattr('app.services.email_service.graph_send_mail', racing_send)
        EmailService._try_send_email(item)
        assert len(graph.sent) == 1
        assert EmailQueue.query.get(item.id).status == 'sent'

    def test_row_held_by_live_worker_is_skipped(self, user, graph):
        item = _queue(user)
        item.status = 'sending'
        item.next_retry_at = now_local() + timedelta(minutes=10)
        db.session.commit()
        assert EmailService.process_queue() == {'processed': 0, 'sent': 0, 'failed': 0}
        assert EmailService._try_send_email(item) is False
        assert graph.sent == [] and EmailQueue.query.get(item.id).status == 'sending'

    def test_row_of_dead_worker_is_reclaimed_after_lease(self, user, graph):
        item = _queue(user)
        item.status = 'sending'
        item.next_retry_at = now_local() - timedelta(minutes=1)
        db.session.commit()
        assert EmailService.process_queue() == {'processed': 1, 'sent': 1, 'failed': 0}
        assert EmailQueue.query.get(item.id).status == 'sent'

    def test_claim_lease_is_stamped_while_sending(self, user, graph, monkeypatch):
        item = _queue(user)
        seen = {}
        real = graph.graph_send_mail

        def spy(*a, **k):
            row = EmailQueue.query.get(item.id)
            seen['status'], seen['lease'] = row.status, row.next_retry_at
            return real(*a, **k)

        monkeypatch.setattr('app.services.email_service.graph_send_mail', spy)
        with freeze_time('2026-03-01 10:00:00'):
            EmailService._try_send_email(item)
            expected = (now_local() + timedelta(minutes=15)).replace(tzinfo=None)
        assert seen['status'] == 'sending'
        assert seen['lease'].replace(tzinfo=None) == expected
        assert item.next_retry_at is None


class TestRetryFailed:
    def test_only_pending_with_attempts(self, user, graph):
        fresh = _queue(user, 'fresh')
        retry = _queue(user, 'retry')
        retry.attempts = 1
        db.session.commit()
        result = EmailService.retry_failed()
        assert result == {'processed': 1, 'sent': 1}
        assert EmailQueue.query.get(fresh.id).status == 'pending'
        assert EmailQueue.query.get(retry.id).status == 'sent'

    def test_attempts_exhausted_not_retried(self, user, graph):
        item = _queue(user)
        item.attempts = 3
        db.session.commit()
        assert EmailService.retry_failed()['processed'] == 0

    def test_no_session(self, user, graph):
        graph.connected = False
        assert 'error' in EmailService.retry_failed()


class TestStats:
    def test_counts(self, user):
        a, b, c = _queue(user), _queue(user), _queue(user)
        b.status = 'sent'
        c.status = 'failed'
        db.session.commit()
        assert EmailService.get_queue_stats() == {
            'pending': 1, 'sent': 1, 'failed': 1, 'total': 3}

    def test_sending_counts_as_pending_and_is_listed(self, user):
        a, b = _queue(user), _queue(user)
        b.status = 'sending'
        db.session.commit()
        assert EmailService.get_queue_stats() == {
            'pending': 2, 'sent': 0, 'failed': 0, 'total': 2}
        assert {i['status'] for i in EmailService.get_pending_emails()['items']} == {'pending', 'sending'}

    def test_pending_listing_excludes_body(self, user):
        _queue(user, body='SECRET-LINK')
        page = EmailService.get_pending_emails()
        assert page['total'] == 1
        assert 'SECRET-LINK' not in str(page)

    def test_pending_listing_pagination(self, user):
        for _ in range(5):
            _queue(user)
        page = EmailService.get_pending_emails(limit=2, offset=4)
        assert page['total'] == 5 and len(page['items']) == 1


class TestPurgeDeliveredBodies:
    def _age(self, item, hours, status):
        item.status = status
        stamp = now_local() - timedelta(hours=hours)
        item.created_at = stamp
        if status == 'sent':
            item.sent_at = stamp
        db.session.commit()

    def test_sent_older_than_24h_is_blanked(self, user):
        item = _queue(user)
        self._age(item, 25, 'sent')
        result = EmailService.purge_delivered_bodies()
        assert result['sent_purged'] == 1 and result['hours'] == BODY_RETENTION_HOURS
        db.session.expire_all()
        assert EmailQueue.query.get(item.id).html_content == PURGED_BODY

    def test_sent_within_window_is_kept(self, user):
        item = _queue(user)
        self._age(item, 23, 'sent')
        assert EmailService.purge_delivered_bodies()['total'] == 0
        assert EmailQueue.query.get(item.id).html_content != PURGED_BODY

    def test_failed_older_than_24h_is_blanked(self, user):
        item = _queue(user)
        self._age(item, 30, 'failed')
        assert EmailService.purge_delivered_bodies()['failed_purged'] == 1

    def test_pending_is_never_purged(self, user):
        item = _queue(user)
        item.created_at = now_local() - timedelta(days=30)
        db.session.commit()
        assert EmailService.purge_delivered_bodies()['total'] == 0
        assert EmailQueue.query.get(item.id).html_content == '<p>cuerpo</p>'

    def test_audit_trail_survives(self, user):
        item = _queue(user, subject='Asunto')
        self._age(item, 48, 'sent')
        EmailService.purge_delivered_bodies()
        db.session.expire_all()
        row = EmailQueue.query.get(item.id)
        assert row.subject == 'Asunto' and row.recipient_email == user.email
        assert row.status == 'sent' and row.sent_at is not None

    def test_idempotent(self, user):
        item = _queue(user)
        self._age(item, 48, 'sent')
        EmailService.purge_delivered_bodies()
        assert EmailService.purge_delivered_bodies()['total'] == 0

    def test_custom_window(self, user):
        item = _queue(user)
        self._age(item, 3, 'sent')
        assert EmailService.purge_delivered_bodies(hours=2)['sent_purged'] == 1

    def test_frozen_clock_boundary(self, user):
        with freeze_time('2026-05-01 12:00:00'):
            item = _queue(user)
            item.status = 'sent'
            item.sent_at = now_local()
            db.session.commit()
        with freeze_time('2026-05-02 11:59:00'):
            assert EmailService.purge_delivered_bodies()['total'] == 0
        with freeze_time('2026-05-02 12:01:00'):
            assert EmailService.purge_delivered_bodies()['total'] == 1


class TestSendEmailAsyncTask:
    def test_sends_and_commits(self, user, graph):
        item = _queue(user)
        notifications.send_email_async.run(item.id)
        db.session.expire_all()
        assert EmailQueue.query.get(item.id).status == 'sent'

    def test_missing_row_is_noop(self, app, graph):
        assert notifications.send_email_async.run(424242) is None

    @pytest.mark.parametrize('status', ['sent', 'failed'])
    def test_terminal_status_is_not_resent(self, user, graph, status):
        item = _queue(user)
        item.status = status
        db.session.commit()
        notifications.send_email_async.run(item.id)
        assert graph.sent == []

    def test_no_session_leaves_pending_without_burning_retries(self, user, graph):
        graph.connected = False
        item = _queue(user)
        result = notifications.send_email_async.run(item.id)
        assert result == {'skipped': True, 'reason': 'no_session'}
        assert EmailQueue.query.get(item.id).attempts == 0

    def test_failure_persists_attempt_then_retries(self, user, graph, monkeypatch):
        graph.status_codes = [500]
        item = _queue(user)
        retried = {}

        def fake_retry(exc=None, countdown=None, **k):
            retried['countdown'] = countdown
            return RuntimeError('retry')

        monkeypatch.setattr(notifications.send_email_async, 'retry', fake_retry)
        with pytest.raises(RuntimeError):
            notifications.send_email_async.run(item.id)
        db.session.expire_all()
        assert EmailQueue.query.get(item.id).attempts == 1
        assert retried['countdown'] == 60


class TestProcessEmailQueueTask:
    def test_idle_when_empty(self, app, graph):
        assert notifications.process_email_queue.run() == {
            'processed': 0, 'sent': 0, 'failed': 0, 'idle': True}

    def test_skips_without_session(self, user, graph):
        _queue(user)
        graph.connected = False
        result = notifications.process_email_queue.run()
        assert result['skipped'] == 'no_session'

    def test_drains_queue(self, user, graph):
        _queue(user)
        _queue(user)
        result = notifications.process_email_queue.run()
        assert result['sent'] == 2
        assert EmailQueue.query.filter_by(status='pending').count() == 0

    def test_respects_limit(self, user, graph):
        for _ in range(3):
            _queue(user)
        assert notifications.process_email_queue.run(limit=2)['processed'] == 2


class TestPurgeTask:
    def test_default_window(self, user):
        item = _queue(user)
        item.status = 'sent'
        item.sent_at = now_local() - timedelta(hours=30)
        db.session.commit()
        result = maintenance.purge_email_bodies.run()
        assert result['sent_purged'] == 1 and result['hours'] == 24

    def test_explicit_window_zero_hours_is_honoured(self, user):
        item = _queue(user)
        item.status = 'sent'
        item.sent_at = now_local() - timedelta(minutes=1)
        db.session.commit()
        assert maintenance.purge_email_bodies.run(hours=0)['sent_purged'] == 1

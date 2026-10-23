"""Session lifetime: server-side idle window vs. absolute cookie cap, and /session-status."""

import time
from datetime import timedelta

from tests.support.factories import make_user


def _set_last_activity(client, seconds_ago):
    with client.session_transaction() as sess:
        sess['last_activity'] = time.time() - seconds_ago


def test_cookie_cap_is_hours_not_the_idle_window(app):
    # The cookie's Expires is judged by the browser's clock; a 17-minute cap
    # logged out active users whose clock ran a few minutes fast.
    assert app.permanent_session_lifetime >= timedelta(hours=1)
    assert app.config.get('SESSION_IDLE_SECONDS', 15 * 60) == 15 * 60


def test_active_session_survives_past_the_old_17_minute_cap(login):
    client = login(make_user('student'))
    # Last request 10 minutes ago: inside the idle window.
    _set_last_activity(client.raw, 10 * 60)
    assert client.get('/api/v1/auth/me').status_code == 200


def test_idle_session_expires_on_the_server(login):
    client = login(make_user('student'))
    _set_last_activity(client.raw, 16 * 60)
    resp = client.get('/api/v1/auth/me')
    assert resp.status_code == 401
    assert resp.get_json()['error']['code'] == 'SESSION_EXPIRED'


def test_session_status_reports_remaining_idle_time(login):
    client = login(make_user('student'))
    _set_last_activity(client.raw, 5 * 60)
    body = client.get('/api/v1/auth/session-status').get_json()['data']
    assert body['idle_limit_seconds'] == 15 * 60
    assert 5 * 60 <= body['idle_seconds'] <= 5 * 60 + 5
    assert 10 * 60 - 5 <= body['remaining_seconds'] <= 10 * 60


def test_session_status_does_not_count_as_activity(login):
    client = login(make_user('student'))
    _set_last_activity(client.raw, 5 * 60)
    client.get('/api/v1/auth/session-status')
    with client.raw.session_transaction() as sess:
        assert time.time() - sess['last_activity'] >= 5 * 60 - 1


def test_session_status_requires_login(client):
    assert client.get('/api/v1/auth/session-status').status_code == 401

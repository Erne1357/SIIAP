"""Idle timeout, user loading, forced password change gating, cookie config."""

import time
from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from app import db
from app.config import Config
from tests.integration.auth_routes import register_test_routes
from tests.integration.auth_support import fake_redis, isolate_globals  # noqa: F401
from tests.support.factories import make_user


@pytest.fixture
def app(app):
    return register_test_routes(app)


def _age(client, seconds):
    with client.raw.session_transaction() as sess:
        sess['last_activity'] = time.time() - seconds


# ── idle timeout ────────────────────────────────────────────────────────────

class TestIdleTimeout:
    def test_api_expired_returns_session_expired_envelope(self, login):
        client = login(make_user('student'))
        _age(client, 16 * 60)
        resp = client.get('/api/v1/auth/me')
        assert resp.status_code == 401
        assert resp.get_json() == {
            'data': None,
            'error': {'code': 'SESSION_EXPIRED', 'message': 'Sesión expirada'},
            'meta': {},
        }

    def test_api_just_inside_window_is_ok(self, login):
        client = login(make_user('student'))
        _age(client, 14 * 60)
        assert client.get('/api/v1/auth/me').status_code == 200

    def test_boundary_just_over_fifteen_minutes(self, login):
        client = login(make_user('student'))
        _age(client, 15 * 60 + 5)
        assert client.get('/api/v1/auth/me').status_code == 401

    def test_expired_session_is_fully_cleared(self, login):
        client = login(make_user('student'))
        _age(client, 20 * 60)
        client.get('/api/v1/auth/me')
        with client.raw.session_transaction() as sess:
            assert '_user_id' not in sess
        assert client.get('/api/v1/auth/me').get_json()['error']['code'] == 'UNAUTHORIZED'

    def test_page_expired_redirects_to_login(self, login):
        client = login(make_user('student'))
        _age(client, 16 * 60)
        resp = client.get('/_t/page')
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/login')

    def test_page_expired_flashes_spanish_message(self, login):
        client = login(make_user('student'))
        _age(client, 16 * 60)
        resp = client.get('/_t/page', follow_redirects=True)
        assert resp.status_code == 200
        assert 'Tu sesión ha expirado por inactividad.' in resp.get_data(as_text=True)

    def test_page_expired_flash_category_warning(self, login):
        client = login(make_user('student'))
        _age(client, 16 * 60)
        client.get('/_t/page')
        with client.raw.session_transaction() as sess:
            assert ['warning', 'Tu sesión ha expirado por inactividad.'] in [list(f) for f in sess['_flashes']]

    def test_api_expiry_does_not_flash(self, login):
        client = login(make_user('student'))
        _age(client, 16 * 60)
        client.get('/api/v1/auth/me')
        with client.raw.session_transaction() as sess:
            assert not sess.get('_flashes')

    def test_activity_refreshes_last_activity(self, login):
        client = login(make_user('student'))
        _age(client, 10 * 60)
        client.get('/api/v1/auth/me')
        with client.raw.session_transaction() as sess:
            assert time.time() - sess['last_activity'] < 60

    def test_sliding_window_keeps_session_alive(self, login):
        client = login(make_user('student'))
        for _ in range(3):
            _age(client, 10 * 60)
            assert client.get('/api/v1/auth/me').status_code == 200

    def test_freezegun_clock_jump(self, login):
        client = login(make_user('student'))
        with client.raw.session_transaction() as sess:
            base = sess['last_activity']
        with freeze_time(datetime.fromtimestamp(base + 16 * 60, tz=timezone.utc)):
            assert client.get('/api/v1/auth/me').status_code == 401

    def test_freezegun_inside_window(self, login):
        client = login(make_user('student'))
        with client.raw.session_transaction() as sess:
            base = sess['last_activity']
        with freeze_time(datetime.fromtimestamp(base + 10 * 60, tz=timezone.utc)):
            assert client.get('/api/v1/auth/me').status_code == 200

    def test_keepalive_is_exempt_from_idle_check(self, login):
        client = login(make_user('student'))
        _age(client, 30 * 60)
        assert client.get('/api/v1/auth/keepalive').status_code == 200
        with client.raw.session_transaction() as sess:
            assert time.time() - sess['last_activity'] < 60

    def test_login_page_exempt_from_idle_check(self, login):
        client = login(make_user('student'))
        _age(client, 30 * 60)
        assert client.get('/login').status_code == 302  # bounced to dashboard, not logged out

    def test_health_exempt_from_idle_check(self, login):
        client = login(make_user('student'))
        _age(client, 30 * 60)
        assert client.get('/health').status_code == 200
        assert client.get('/api/v1/auth/me').status_code == 401  # clock was NOT refreshed

    def test_anonymous_never_gets_session_expired(self, client):
        assert client.get('/api/v1/auth/me').get_json()['error']['code'] == 'UNAUTHORIZED'

    def test_permanent_session_lifetime(self, app):
        # Absolute cookie cap; inactivity is enforced separately on the server
        # (SESSION_IDLE_SECONDS). It was 17 minutes, which tied active sessions
        # to the browser's clock — see test_session_lifetime.py.
        assert app.permanent_session_lifetime.total_seconds() == 12 * 3600

    def test_expired_session_csrf_token_dropped(self, login):
        client = login(make_user('student'))
        _age(client, 20 * 60)
        client.get('/api/v1/auth/me')
        assert client.post('/api/v1/_t/echo').status_code == 400


# ── load_user ───────────────────────────────────────────────────────────────

class TestLoadUser:
    def _with_session(self, client, value):
        with client.session_transaction() as sess:
            sess['_user_id'] = value
            sess['_fresh'] = True
            sess['last_activity'] = time.time()

    @pytest.mark.parametrize('bad', ['abc', '', '1.5', 'NaN', 'null', '1; DROP TABLE user', ' ', '1e3'])
    def test_malformed_user_id_is_anonymous_on_api(self, client, bad):
        self._with_session(client, bad)
        resp = client.get('/api/v1/auth/me')
        assert resp.status_code == 401
        assert resp.get_json()['error']['code'] == 'UNAUTHORIZED'

    def test_malformed_user_id_does_not_break_login_page(self, client):
        self._with_session(client, 'garbage')
        assert client.get('/login').status_code == 200

    def test_malformed_user_id_does_not_break_logout_get(self, client):
        self._with_session(client, 'garbage')
        assert client.get('/api/v1/auth/logout').status_code == 401

    def test_malformed_user_id_page_redirects_to_login(self, client):
        self._with_session(client, 'garbage')
        resp = client.get('/_t/page')
        assert resp.status_code == 302 and resp.headers['Location'].endswith('/login')

    def test_uuid_string_is_not_a_valid_session_id(self, client):
        user = make_user('student')
        db.session.commit()
        self._with_session(client, str(user.uuid))
        assert client.get('/api/v1/auth/me').status_code == 401

    def test_nonexistent_user_id_is_anonymous(self, client):
        self._with_session(client, '987654')
        assert client.get('/api/v1/auth/me').status_code == 401

    def test_negative_user_id_is_anonymous(self, client):
        self._with_session(client, '-1')
        assert client.get('/api/v1/auth/me').status_code == 401

    def test_inactive_user_is_anonymous(self, client):
        user = make_user('student', is_active=False)
        db.session.commit()
        self._with_session(client, str(user.id))
        assert client.get('/api/v1/auth/me').status_code == 401

    def test_deactivating_user_kills_existing_session(self, login):
        user = make_user('student')
        client = login(user)
        assert client.get('/api/v1/auth/me').status_code == 200
        user.is_active = False
        db.session.commit()
        resp = client.get('/api/v1/auth/me')
        assert resp.status_code == 401
        assert resp.get_json()['error']['code'] == 'UNAUTHORIZED'

    def test_deactivated_session_cannot_be_kept_alive(self, login):
        user = make_user('student')
        client = login(user)
        user.is_active = False
        db.session.commit()
        assert client.get('/api/v1/auth/keepalive').status_code == 401

    def test_valid_session_loads_user(self, login):
        user = make_user('student', username='ana')
        assert login(user).get('/api/v1/auth/me').get_json()['data']['username'] == 'ana'

    def test_deleted_user_is_anonymous(self, login):
        user = make_user('student')
        client = login(user)
        db.session.delete(user)
        db.session.commit()
        assert client.get('/api/v1/auth/me').status_code == 401

    def test_unauthorized_page_flashes_login_message(self, client):
        assert client.get('/_t/page').status_code == 302
        with client.session_transaction() as sess:
            flashes = [list(f) for f in sess['_flashes']]
        assert ['warning', 'Por favor, inicia sesión para acceder a esta página.'] in flashes

    def test_unauthorized_page_follow_shows_message(self, client):
        resp = client.get('/_t/page', follow_redirects=True)
        assert resp.status_code == 200
        assert 'Por favor, inicia sesión' in resp.get_data(as_text=True)


# ── must_change_password gating ─────────────────────────────────────────────

class TestMustChangePassword:
    @pytest.fixture
    def pending(self, login):
        return login(make_user('student', must_change_password=True))

    def test_api_blocked_with_403_envelope(self, pending):
        resp = pending.get('/api/v1/_t/echo')
        assert resp.status_code == 403
        body = resp.get_json()
        assert body['data'] is None
        assert body['error']['code'] == 'PASSWORD_CHANGE_REQUIRED'
        assert body['error']['must_change_password'] is True
        assert body['flash'][0]['message'] == 'Debes cambiar tu contraseña antes de continuar'

    @pytest.mark.parametrize('method', ['post', 'put', 'patch', 'delete'])
    def test_api_mutations_blocked(self, pending, method):
        resp = getattr(pending, method)('/api/v1/_t/echo')
        assert resp.status_code == 403
        assert resp.get_json()['error']['code'] == 'PASSWORD_CHANGE_REQUIRED'

    def test_page_navigation_pinned_to_dashboard(self, pending):
        resp = pending.get('/_t/page')
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/user/dashboard')

    def test_page_navigation_flashes_spanish_warning(self, pending):
        pending.get('/_t/page')
        with pending.raw.session_transaction() as sess:
            flashes = [list(f) for f in sess['_flashes']]
        assert ['warning', 'Debes cambiar tu contraseña antes de continuar.'] in flashes

    def test_open_route_is_pinned_too(self, pending):
        assert pending.get('/_t/open').status_code == 302

    def test_xhr_on_page_path_gets_json(self, pending):
        resp = pending.get('/_t/page', headers={'X-Requested-With': 'XMLHttpRequest'})
        assert resp.status_code == 403
        assert resp.get_json()['error']['code'] == 'PASSWORD_CHANGE_REQUIRED'

    def test_json_request_on_page_path_gets_json(self, pending):
        assert pending.post('/_t/form', json={}).status_code == 403

    def test_dashboard_is_not_redirected_to_itself(self, pending):
        resp = pending.get('/user/dashboard')
        assert not resp.headers.get('Location', '').endswith('/user/dashboard')

    @pytest.mark.parametrize('path', [
        '/api/v1/auth/me',
        '/api/v1/auth/keepalive',
        '/api/v1/auth/reset-password/sometoken/info',
    ])
    def test_allow_listed_api_get_paths(self, pending, path):
        resp = pending.get(path)
        body = resp.get_json() or {}
        assert (body.get('error') or {}).get('code') != 'PASSWORD_CHANGE_REQUIRED'

    def test_me_exposes_flag_to_the_modal(self, pending):
        assert pending.get('/api/v1/auth/me').get_json()['data']['must_change_password'] is True

    def test_keepalive_reachable(self, pending):
        assert pending.get('/api/v1/auth/keepalive').status_code == 200

    def test_change_password_reachable(self, pending):
        assert pending.post('/api/v1/auth/change-password', json={}).status_code == 400

    def test_logout_reachable(self, pending):
        assert pending.post('/api/v1/auth/logout').status_code == 200

    def test_reset_password_post_reachable(self, pending):
        resp = pending.post('/api/v1/auth/reset-password/nope', json={})
        assert resp.status_code == 400  # VALIDATION_ERROR from the view itself

    def test_static_reachable(self, pending):
        assert pending.get('/static/css/base.css').status_code == 200

    def test_static_missing_is_404_not_gate(self, pending):
        assert pending.get('/static/nope.css').status_code == 404

    def test_health_reachable(self, pending):
        assert pending.get('/health').status_code == 200

    def test_ready_reachable(self, pending, fake_redis):
        resp = pending.get('/ready')
        assert resp.status_code in (200, 503)
        assert resp.is_json

    def test_login_page_not_gated(self, pending):
        resp = pending.get('/login')
        assert resp.status_code == 302
        with pending.raw.session_transaction() as sess:
            assert not sess.get('_flashes')

    def test_reset_password_page_reachable_and_logs_out(self, pending):
        assert pending.get('/reset-password/sometoken').status_code == 200
        assert pending.get('/api/v1/auth/me').status_code == 401

    def test_changing_password_lifts_the_gate(self, login):
        client = login(make_user('student', must_change_password=True))
        assert client.get('/api/v1/_t/echo').status_code == 403
        resp = client.post('/api/v1/auth/change-password', json={
            'current_password': 'Test1234!', 'new_password': 'Nueva#Clave9',
            'confirm_password': 'Nueva#Clave9'})
        assert resp.status_code == 200
        assert client.get('/api/v1/_t/echo').status_code == 200

    def test_normal_user_not_gated(self, login):
        client = login(make_user('student'))
        assert client.get('/api/v1/_t/echo').status_code == 200
        assert client.get('/_t/page').status_code == 200

    def test_anonymous_not_gated(self, client):
        assert client.get('/api/v1/_t/echo').status_code == 200

    def test_gate_runs_before_view_for_permission_routes(self, login):
        client = login(make_user('student', must_change_password=True))
        assert client.get('/api/v1/_t/perm').get_json()['error']['code'] == 'PASSWORD_CHANGE_REQUIRED'

    # Regression (fixed): allow-list is a path-prefix match ('/api/v1/auth/me' also admits
    # '/api/v1/auth/menu...', '/health' admits '/healthz...'); the code comment says paths are not
    # matched by prefix by accident (app/__init__.py check_password_change_required)
    def test_allow_list_does_not_match_lookalike_prefix(self, app, pending):
        app.add_url_rule('/api/v1/auth/menu-x', 't_lookalike',
                         lambda: {'data': 'leak', 'error': None, 'meta': {}})
        resp = pending.get('/api/v1/auth/menu-x')
        assert resp.status_code == 403


# ── cookie / session configuration ──────────────────────────────────────────

class TestCookieConfig:
    def test_session_cookie_httponly(self):
        assert Config.SESSION_COOKIE_HTTPONLY is True

    def test_session_cookie_samesite_lax(self):
        assert Config.SESSION_COOKIE_SAMESITE == 'Lax'

    def test_remember_cookie_httponly_and_lax(self):
        assert Config.REMEMBER_COOKIE_HTTPONLY is True
        assert Config.REMEMBER_COOKIE_SAMESITE == 'Lax'

    def test_cookie_name_is_app_specific(self):
        assert Config.SESSION_COOKIE_NAME == 'siiap_session'

    def test_remember_secure_matches_session_secure(self):
        assert Config.REMEMBER_COOKIE_SECURE == Config.SESSION_COOKIE_SECURE

    def test_set_cookie_header_flags_on_login(self, app, fake_redis):
        app.config.update(SESSION_COOKIE_HTTPONLY=Config.SESSION_COOKIE_HTTPONLY,
                          SESSION_COOKIE_SAMESITE=Config.SESSION_COOKIE_SAMESITE,
                          SESSION_COOKIE_NAME=Config.SESSION_COOKIE_NAME)
        make_user('student', username='ana')
        db.session.commit()
        resp = app.test_client().post('/api/v1/auth/login',
                                      json={'username': 'ana', 'password': 'Test1234!'})
        cookie = resp.headers['Set-Cookie']
        assert cookie.startswith('siiap_session=')
        assert 'HttpOnly' in cookie
        assert 'SameSite=Lax' in cookie
        assert 'Test1234' not in cookie

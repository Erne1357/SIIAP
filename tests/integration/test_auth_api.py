"""Integration tests for app/routes/api/auth_api.py."""

import json

import pytest
from freezegun import freeze_time

from app import db
from app.models.log import Log
from app.models.user import User
from app.routes.api.auth_api import validate_password_strength
from app.services.auth_audit_service import AuthAuditService
from tests.integration.auth_support import (  # noqa: F401
    GOOD_PASSWORD, LOGIN_URL, NEW_PASSWORD, assert_envelope, audit_rows, fake_redis,
    isolate_globals, login_via_api, make_token, post_login,
)
from tests.support.factories import make_user
from tests.support.fixtures import seed_csrf, signed_csrf_token

INVALID_BODY = {
    'data': None,
    'error': {'code': 'INVALID_CREDENTIALS', 'message': 'Usuario o contraseña inválidos'},
    'meta': {},
}


# ── login: success ──────────────────────────────────────────────────────────

class TestLoginSuccess:
    def test_returns_envelope_and_user_data(self, client, fake_redis):
        user = make_user('student', username='ana')
        db.session.commit()
        resp = post_login(client, 'ana', GOOD_PASSWORD)
        assert resp.status_code == 200
        body = resp.get_json()
        assert_envelope(body)
        assert body['error'] is None
        data = body['data']
        assert data['username'] == 'ana'
        assert data['role'] == 'student'
        assert data['must_change_password'] is False
        assert data['id'] == str(user.uuid)

    def test_response_never_exposes_hash(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        raw = post_login(client, 'ana', GOOD_PASSWORD).get_data(as_text=True)
        assert 'password' not in json.loads(raw)['data']
        assert 'pbkdf2' not in raw

    def test_returns_csrf_token_and_stores_it_in_session(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        token = post_login(client, 'ana', GOOD_PASSWORD).get_json()['data']['csrf_token']
        assert token
        with client.session_transaction() as sess:
            raw = sess['csrf_token']
        # The client gets the signed copy of the session's raw token.
        assert token != raw
        from itsdangerous import URLSafeTimedSerializer
        assert URLSafeTimedSerializer(
            client.application.secret_key, salt='wtf-csrf-token').loads(token) == raw

    def test_sets_session_and_last_activity(self, client, fake_redis):
        user = make_user('student', username='ana')
        db.session.commit()
        post_login(client, 'ana', GOOD_PASSWORD)
        with client.session_transaction() as sess:
            assert sess['_user_id'] == str(user.id)
            assert sess['last_activity'] > 0

    def test_updates_last_login(self, client, fake_redis):
        user = make_user('student', username='ana')
        db.session.commit()
        before = user.last_login
        with freeze_time('2099-01-01 12:00:00'):
            post_login(client, 'ana', GOOD_PASSWORD)
        db.session.expire_all()
        assert User.query.get(user.id).last_login.year == 2099
        assert before.year != 2099

    def test_session_works_afterwards(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        post_login(client, 'ana', GOOD_PASSWORD)
        assert client.get('/api/v1/auth/me').status_code == 200

    def test_username_is_stripped(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        assert post_login(client, '  ana  ', GOOD_PASSWORD).status_code == 200

    def test_reports_must_change_password_flag(self, client, fake_redis):
        make_user('student', username='ana', must_change_password=True)
        db.session.commit()
        data = post_login(client, 'ana', GOOD_PASSWORD).get_json()['data']
        assert data['must_change_password'] is True

    def test_login_is_csrf_exempt(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        assert client.post(LOGIN_URL, json={'username': 'ana', 'password': GOOD_PASSWORD}).status_code == 200

    def test_each_login_rotates_csrf_token(self, app, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        t1 = post_login(app.test_client(), 'ana', GOOD_PASSWORD).get_json()['data']['csrf_token']
        t2 = post_login(app.test_client(), 'ana', GOOD_PASSWORD).get_json()['data']['csrf_token']
        assert t1 != t2


# ── login: failures are indistinguishable ───────────────────────────────────

class TestLoginFailures:
    def test_wrong_password(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        resp = post_login(client, 'ana', 'incorrecta')
        assert resp.status_code == 401
        assert resp.get_json() == INVALID_BODY

    def test_unknown_user(self, client, fake_redis):
        resp = post_login(client, 'fantasma', GOOD_PASSWORD)
        assert resp.status_code == 401
        assert resp.get_json() == INVALID_BODY

    def test_inactive_user_correct_password(self, client, fake_redis):
        make_user('student', username='ana', is_active=False)
        db.session.commit()
        resp = post_login(client, 'ana', GOOD_PASSWORD)
        assert resp.status_code == 401
        assert resp.get_json() == INVALID_BODY

    def test_three_failure_modes_are_byte_identical(self, app, fake_redis):
        make_user('student', username='ana')
        make_user('student', username='baja', is_active=False)
        db.session.commit()
        bodies = {
            post_login(app.test_client(), 'ana', 'mala').get_data(),
            post_login(app.test_client(), 'nadie', 'mala').get_data(),
            post_login(app.test_client(), 'baja', GOOD_PASSWORD).get_data(),
        }
        assert len(bodies) == 1

    def test_failures_do_not_create_a_session(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        post_login(client, 'ana', 'mala')
        assert client.get('/api/v1/auth/me').status_code == 401

    def test_inactive_user_gets_no_session(self, client, fake_redis):
        make_user('student', username='ana', is_active=False)
        db.session.commit()
        post_login(client, 'ana', GOOD_PASSWORD)
        assert client.get('/api/v1/auth/me').status_code == 401

    @pytest.mark.parametrize('payload', [
        {}, {'username': 'ana'}, {'password': 'x'}, {'username': '', 'password': ''},
        {'username': '   ', 'password': 'x'}, {'username': None, 'password': None},
    ])
    def test_missing_or_blank_fields(self, client, fake_redis, payload):
        # Documented behaviour: a credential-less request is a 401, not a 400.
        resp = client.post(LOGIN_URL, json=payload)
        assert resp.status_code == 401
        assert resp.get_json() == INVALID_BODY

    def test_non_json_body(self, client, fake_redis):
        resp = client.post(LOGIN_URL, data='username=ana&password=x')
        assert resp.status_code == 401
        assert resp.get_json() == INVALID_BODY

    def test_malformed_json_body(self, client, fake_redis):
        resp = client.post(LOGIN_URL, data='{not json', content_type='application/json')
        assert resp.status_code == 401

    def test_credential_less_requests_never_touch_throttle(self, client, fake_redis):
        for _ in range(12):
            assert client.post(LOGIN_URL, json={}).status_code == 401
        assert list(fake_redis.scan_iter('siiap:loginfail:*')) == []

    def test_failed_login_does_not_set_last_login(self, client, fake_redis):
        user = make_user('student', username='ana')
        db.session.commit()
        before = user.last_login
        with freeze_time('2099-01-01 12:00:00'):
            post_login(client, 'ana', 'mala')
        db.session.expire_all()
        assert User.query.get(user.id).last_login == before

    def test_get_login_not_allowed(self, client):
        assert client.get(LOGIN_URL).status_code == 405

    def test_login_works_when_redis_is_down(self, client):
        """Fail open: Redis unreachable (conftest points at a closed port)."""
        make_user('student', username='ana')
        db.session.commit()
        assert post_login(client, 'ana', GOOD_PASSWORD).status_code == 200


# ── login: throttling ───────────────────────────────────────────────────────

class TestLoginThrottle:
    def _fail(self, client, n, username='ana'):
        return [post_login(client, username, 'mala').status_code for _ in range(n)]

    def test_first_five_attempts_are_401(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        assert self._fail(client, 5) == [401] * 5

    def test_sixth_attempt_is_429(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        assert self._fail(client, 6)[-1] == 429

    def test_429_envelope_and_retry_after(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        self._fail(client, 5)
        resp = post_login(client, 'ana', 'mala')
        assert resp.status_code == 429
        assert resp.get_json()['error']['code'] == 'RATE_LIMITED'
        assert resp.get_json()['data'] is None
        assert resp.headers['Retry-After'] == '60'

    def test_correct_password_is_also_blocked_during_penalty(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        self._fail(client, 6)
        assert post_login(client, 'ana', GOOD_PASSWORD).status_code == 429

    def test_throttle_is_per_username(self, app, fake_redis):
        make_user('student', username='ana')
        make_user('student', username='beto')
        db.session.commit()
        self._fail(app.test_client(), 6)
        assert post_login(app.test_client(), 'beto', GOOD_PASSWORD).status_code == 200

    def test_username_digest_is_case_insensitive(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        for _ in range(5):
            post_login(client, 'ANA', 'mala')
        assert post_login(client, 'ana', 'mala').status_code == 429

    def test_successful_login_clears_counter(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        self._fail(client, 4)
        assert post_login(client, 'ana', GOOD_PASSWORD).status_code == 200
        assert list(fake_redis.scan_iter('siiap:loginfail:u:*')) == []
        client.get('/api/v1/auth/logout')
        assert self._fail(client, 5) == [401] * 5

    def test_unknown_usernames_are_throttled_too(self, client, fake_redis):
        assert self._fail(client, 6, username='fantasma')[-1] == 429

    def test_delay_escalates(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        self._fail(client, 6)
        for key in fake_redis.scan_iter('siiap:loginfail:ub:*'):
            fake_redis.delete(key)
        resp = post_login(client, 'ana', 'mala')
        assert resp.status_code == 429
        assert resp.headers['Retry-After'] == '300'

    def test_attempts_during_penalty_are_not_counted(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        self._fail(client, 6)
        key = next(fake_redis.scan_iter('siiap:loginfail:u:*'))
        before = int(fake_redis.get(key))
        self._fail(client, 3)
        assert int(fake_redis.get(key)) == before

    def test_penalty_expires(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        self._fail(client, 6)
        for key in list(fake_redis.scan_iter('siiap:loginfail:u*')):
            fake_redis.delete(key)
        assert post_login(client, 'ana', GOOD_PASSWORD).status_code == 200

    def test_blocked_attempts_write_no_audit_rows(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        self._fail(client, 6)
        rows_before = Log.query.count()
        self._fail(client, 5)
        assert Log.query.count() == rows_before

    def test_redis_keys_do_not_contain_plain_username(self, client, fake_redis):
        make_user('student', username='ana_secreta')
        db.session.commit()
        self._fail(client, 1, username='ana_secreta')
        assert all('ana_secreta' not in k for k in fake_redis.keys('*'))

    def test_custom_threshold_via_config(self, app, fake_redis):
        app.config['LOGIN_THROTTLE_USER_MAX'] = 2
        make_user('student', username='ana')
        db.session.commit()
        codes = [post_login(app.test_client(), 'ana', 'mala').status_code for _ in range(3)]
        assert codes == [401, 401, 429]


# ── login: audit trail ──────────────────────────────────────────────────────

class TestLoginAudit:
    def test_success_row(self, client, fake_redis):
        user = make_user('student', username='ana')
        db.session.commit()
        post_login(client, 'ana', GOOD_PASSWORD, headers={'User-Agent': 'pytest-agent'})
        rows = audit_rows(AuthAuditService.ACTION_LOGIN_SUCCESS)
        assert len(rows) == 1
        assert rows[0].user_id == user.id
        payload = json.loads(rows[0].description)
        assert payload['username'] == 'ana'
        assert payload['user_agent'] == 'pytest-agent'

    def test_failure_row_for_known_user(self, client, fake_redis):
        user = make_user('student', username='ana')
        db.session.commit()
        post_login(client, 'ana', 'mala')
        rows = audit_rows(AuthAuditService.ACTION_LOGIN_FAILED)
        assert len(rows) == 1 and rows[0].user_id == user.id
        assert json.loads(rows[0].description)['reason'] == 'bad_password'

    def test_failure_row_for_unknown_user_has_null_user_id(self, client, fake_redis):
        post_login(client, 'fantasma', 'mala')
        rows = audit_rows(AuthAuditService.ACTION_LOGIN_FAILED)
        assert len(rows) == 1 and rows[0].user_id is None
        assert json.loads(rows[0].description)['reason'] == 'unknown_user'

    def test_failure_row_for_inactive_account(self, client, fake_redis):
        make_user('student', username='ana', is_active=False)
        db.session.commit()
        post_login(client, 'ana', GOOD_PASSWORD)
        rows = audit_rows(AuthAuditService.ACTION_LOGIN_FAILED)
        assert json.loads(rows[0].description)['reason'] == 'inactive_account'

    def test_ip_stored_as_prefix_only(self, client, fake_redis):
        post_login(client, 'fantasma', 'mala')
        row = audit_rows()[0]
        assert json.loads(row.description)['ip_prefix'] == '127.0.0.0/24'
        assert '127.0.0.1' not in row.description

    def test_password_never_in_audit(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        post_login(client, 'ana', 'SuperSecreta#1')
        assert all('SuperSecreta#1' not in (r.description or '') for r in audit_rows())

    def test_only_first_failure_and_threshold_are_persisted(self, client, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        for _ in range(5):
            post_login(client, 'ana', 'mala')
        assert [r.action for r in audit_rows()] == [
            AuthAuditService.ACTION_LOGIN_FAILED,
            AuthAuditService.ACTION_LOGIN_THROTTLED,
        ]

    def test_user_agent_truncated(self, client, fake_redis):
        post_login(client, 'fantasma', 'mala', headers={'User-Agent': 'A' * 500})
        assert len(json.loads(audit_rows()[0].description)['user_agent']) <= 120

    def test_long_username_truncated(self, client, fake_redis):
        post_login(client, 'u' * 300, 'mala')
        assert len(json.loads(audit_rows()[0].description)['username']) <= 64

    def test_audit_failure_never_breaks_login(self, client, fake_redis, monkeypatch):
        make_user('student', username='ana')
        db.session.commit()

        def boom(*a, **k):
            raise RuntimeError('db down')
        monkeypatch.setattr(Log, '__init__', boom)
        assert post_login(client, 'ana', 'mala').status_code == 401

    def test_known_and_unknown_user_audit_same_shape(self, app, fake_redis):
        make_user('student', username='ana')
        db.session.commit()
        post_login(app.test_client(), 'ana', 'mala')
        post_login(app.test_client(), 'nadie', 'mala')
        a, b = audit_rows()
        assert a.action == b.action
        assert set(json.loads(a.description)) == set(json.loads(b.description))


# ── logout ──────────────────────────────────────────────────────────────────

class TestLogout:
    def test_post_returns_json_and_clears_session(self, login):
        client = login(make_user('student'))
        resp = client.post('/api/v1/auth/logout')
        assert resp.status_code == 200
        assert resp.get_json()['flash'][0]['message'] == 'Has cerrado sesión.'
        assert client.get('/api/v1/auth/me').status_code == 401

    def test_get_redirects_to_login(self, login):
        client = login(make_user('student'))
        resp = client.get('/api/v1/auth/logout')
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/login')

    def test_get_clears_session(self, login):
        client = login(make_user('student'))
        client.get('/api/v1/auth/logout')
        assert client.get('/api/v1/auth/me').status_code == 401

    def test_logout_drops_csrf_and_last_activity(self, login):
        client = login(make_user('student'))
        client.post('/api/v1/auth/logout')
        with client.raw.session_transaction() as sess:
            assert 'csrf_token' not in sess
            assert 'last_activity' not in sess
            assert '_user_id' not in sess

    def test_logout_drops_pending_flashes(self, login):
        client = login(make_user('student'))
        with client.raw.session_transaction() as sess:
            sess['_flashes'] = [('warning', 'viejo')]
        client.post('/api/v1/auth/logout')
        with client.raw.session_transaction() as sess:
            assert '_flashes' not in sess

    def test_anonymous_post_logout_is_rejected(self, client):
        assert client.post('/api/v1/auth/logout').status_code in (400, 401)

    def test_anonymous_get_logout_is_json_401(self, client):
        resp = client.get('/api/v1/auth/logout')
        assert resp.status_code == 401
        assert resp.get_json()['error']['code'] == 'UNAUTHORIZED'

    def test_post_logout_requires_csrf(self, login):
        client = login(make_user('student'))
        assert client.raw.post('/api/v1/auth/logout').status_code == 400

    def test_logout_allowed_while_password_change_pending(self, login):
        client = login(make_user('student', must_change_password=True))
        assert client.post('/api/v1/auth/logout').status_code == 200


# ── /me and /keepalive ──────────────────────────────────────────────────────

class TestMeAndKeepalive:
    def test_me_payload(self, login):
        user = make_user('student', username='ana', email='ana@x.test')
        client = login(user)
        resp = client.get('/api/v1/auth/me')
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert data['username'] == 'ana'
        assert data['email'] == 'ana@x.test'
        assert data['role'] == 'student'
        assert data['id'] == str(user.uuid)
        assert data['csrf_token'] == signed_csrf_token(client.raw.application, 'test-csrf-token')
        assert 'password' not in data

    def test_me_anonymous_401_envelope(self, client):
        resp = client.get('/api/v1/auth/me')
        assert resp.status_code == 401
        assert resp.get_json() == {
            'data': None,
            'error': {'code': 'UNAUTHORIZED', 'message': 'No autenticado'},
            'meta': {},
        }

    def test_keepalive_ok(self, login):
        resp = login(make_user('student')).get('/api/v1/auth/keepalive')
        assert resp.status_code == 200
        assert resp.get_json()['data'] == 'OK'

    def test_keepalive_anonymous_401(self, client):
        assert client.get('/api/v1/auth/keepalive').status_code == 401

    def test_keepalive_refreshes_last_activity(self, login):
        client = login(make_user('student'))
        with client.raw.session_transaction() as sess:
            sess['last_activity'] = 1.0
        client.get('/api/v1/auth/keepalive')
        with client.raw.session_transaction() as sess:
            assert sess['last_activity'] > 1.0


# ── change-password ─────────────────────────────────────────────────────────

CP = '/api/v1/auth/change-password'


def _cp(client, current=GOOD_PASSWORD, new=NEW_PASSWORD, confirm=None):
    return client.post(CP, json={
        'current_password': current, 'new_password': new,
        'confirm_password': new if confirm is None else confirm,
    })


class TestChangePassword:
    def test_success(self, login):
        user = make_user('student', must_change_password=True)
        resp = _cp(login(user))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['data']['password_changed'] is True
        assert body['meta']['must_change_password'] is False
        assert body['flash'][0]['level'] == 'success'
        db.session.expire_all()
        assert User.query.get(user.id).must_change_password is False

    def test_new_password_works_for_login(self, app, login, fake_redis):
        user = make_user('student', username='ana')
        _cp(login(user))
        assert post_login(app.test_client(), 'ana', NEW_PASSWORD).status_code == 200
        assert post_login(app.test_client(), 'ana', GOOD_PASSWORD).status_code == 401

    def test_password_not_stored_in_clear(self, login):
        user = make_user('student')
        _cp(login(user))
        db.session.expire_all()
        assert User.query.get(user.id).password != NEW_PASSWORD

    def test_anonymous_rejected(self, client):
        assert client.post(CP, json={}).status_code in (400, 401)

    def test_anonymous_with_csrf_is_401(self, client):
        header = seed_csrf(client, 'tok')
        resp = client.post(CP, json={}, headers={'X-CSRFToken': header})
        assert resp.status_code == 401

    @pytest.mark.parametrize('missing', ['current_password', 'new_password', 'confirm_password'])
    def test_missing_field(self, login, missing):
        client = login(make_user('student'))
        payload = {'current_password': GOOD_PASSWORD, 'new_password': NEW_PASSWORD,
                   'confirm_password': NEW_PASSWORD}
        payload.pop(missing)
        resp = client.post(CP, json=payload)
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'VALIDATION_ERROR'

    def test_empty_body(self, login):
        assert login(make_user('student')).post(CP, json={}).status_code == 400

    def test_wrong_current_password(self, login):
        resp = _cp(login(make_user('student')), current='incorrecta')
        assert resp.status_code == 401
        assert resp.get_json()['error']['code'] == 'INVALID_PASSWORD'

    def test_mismatch(self, login):
        resp = _cp(login(make_user('student')), confirm='Otra#Clave99')
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'PASSWORD_MISMATCH'

    @pytest.mark.parametrize('weak,fragment', [
        ('Ab1!', '8 caracteres'),
        ('minuscula1!', 'mayúscula'),
        ('MAYUSCULA1!', 'minúscula'),
        ('SinNumero!!', 'número'),
        ('SinEspecial1', 'especial'),
    ])
    def test_weak_passwords(self, login, weak, fragment):
        resp = _cp(login(make_user('student')), new=weak)
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['error']['code'] == 'WEAK_PASSWORD'
        assert fragment in body['error']['message']

    def test_same_password_rejected(self, login):
        resp = _cp(login(make_user('student')), new=GOOD_PASSWORD)
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'SAME_PASSWORD'

    def test_failed_change_keeps_flag(self, login):
        user = make_user('student', must_change_password=True)
        _cp(login(user), new='debil')
        db.session.expire_all()
        assert User.query.get(user.id).must_change_password is True

    def test_wrong_current_checked_before_mismatch(self, login):
        resp = _cp(login(make_user('student')), current='mala', confirm='x')
        assert resp.get_json()['error']['code'] == 'INVALID_PASSWORD'

    def test_requires_csrf(self, login):
        client = login(make_user('student'))
        resp = client.raw.post(CP, json={'current_password': GOOD_PASSWORD,
                                         'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD})
        assert resp.status_code == 400

    def test_whitespace_is_stripped_from_passwords(self, login):
        resp = _cp(login(make_user('student')), new='  ' + NEW_PASSWORD + '  ', confirm=NEW_PASSWORD)
        assert resp.status_code == 200

    def test_records_history(self, login):
        from app.models.user_history import UserHistory
        user = make_user('student')
        _cp(login(user))
        assert UserHistory.query.filter_by(user_id=user.id).count() >= 1

    def test_allowed_during_forced_change(self, login):
        client = login(make_user('student', must_change_password=True))
        assert _cp(client).status_code == 200


class TestValidatePasswordStrength:
    @pytest.mark.parametrize('pw,ok', [
        ('Abcdef1!', True), ('Abcdef1', False), ('abcdef1!', False), ('ABCDEF1!', False),
        ('Abcdefg!', False), ('Abcdefg1', False), ('', False), ('A1!a', False),
    ])
    def test_rules(self, pw, ok):
        assert validate_password_strength(pw)[0] is ok


# ── reset-password by token ─────────────────────────────────────────────────

class TestResetPasswordInfo:
    def _url(self, token):
        return f'/api/v1/auth/reset-password/{token}/info'

    def test_valid_token(self, client):
        prt = make_token(make_user('student', username='ana'))
        resp = client.get(self._url(prt.token))
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert data['username'] == 'ana'
        assert data['purpose'] == 'set_password'
        assert data['expires_at']

    def test_info_does_not_leak_password_or_token(self, client):
        prt = make_token(make_user('student'))
        raw = client.get(self._url(prt.token)).get_data(as_text=True)
        assert 'pbkdf2' not in raw and prt.token not in raw

    def test_unknown_token(self, client):
        resp = client.get(self._url('no-existe'))
        assert resp.status_code == 404
        assert resp.get_json()['error']['code'] == 'TOKEN_NOT_FOUND'

    def test_expired_token(self, client):
        prt = make_token(make_user('student'), expired=True)
        resp = client.get(self._url(prt.token))
        assert resp.status_code == 410
        assert resp.get_json()['error']['code'] == 'TOKEN_EXPIRED'

    def test_used_token(self, client):
        prt = make_token(make_user('student'), used=True)
        resp = client.get(self._url(prt.token))
        assert resp.status_code == 410
        assert resp.get_json()['error']['code'] == 'TOKEN_USED'

    def test_token_expires_with_time(self, client):
        prt = make_token(make_user('student'))
        with freeze_time('2099-01-01'):
            assert client.get(self._url(prt.token)).status_code == 410

    def test_reset_purpose_reported(self, client):
        prt = make_token(make_user('student'), purpose='reset_password')
        assert client.get(self._url(prt.token)).get_json()['data']['purpose'] == 'reset_password'

    def test_reachable_while_password_change_pending(self, login):
        user = make_user('student', must_change_password=True)
        prt = make_token(user)
        assert login(user).get(self._url(prt.token)).status_code == 200


class TestResetPasswordSet:
    def _post(self, client, token, new=NEW_PASSWORD, confirm=None, csrf=True):
        header = seed_csrf(client, 'tok') if csrf else None
        return client.post(
            f'/api/v1/auth/reset-password/{token}',
            json={'new_password': new, 'confirm_password': new if confirm is None else confirm},
            headers={'X-CSRFToken': header} if csrf else {},
        )

    # Regression (fixed): password_reset_service.consume_token logs action 'password_set_via_token',
    # which UserHistoryService.ACTIONS rejects -> every token set-password returns 500 SERVER_ERROR
    # (app/services/password_reset_service.py:240)
    def test_success_sets_password_and_consumes_token(self, app, client, fake_redis):
        user = make_user('student', username='ana', must_change_password=True)
        prt = make_token(user)
        resp = self._post(client, prt.token)
        assert resp.status_code == 200
        assert resp.get_json()['data'] == {'username': 'ana'}
        db.session.expire_all()
        fresh = User.query.get(user.id)
        assert fresh.must_change_password is False
        assert fresh.password != NEW_PASSWORD
        assert post_login(app.test_client(), 'ana', NEW_PASSWORD).status_code == 200

    # Regression (fixed): password_reset_service.consume_token logs action 'password_set_via_token',
    # which UserHistoryService.ACTIONS rejects -> every token set-password returns 500 SERVER_ERROR
    # (app/services/password_reset_service.py:240)
    def test_token_is_single_use(self, client):
        prt = make_token(make_user('student'))
        assert self._post(client, prt.token).status_code == 200
        resp = self._post(client, prt.token)
        assert resp.status_code == 410
        assert resp.get_json()['error']['code'] == 'TOKEN_USED'

    def test_expired_token(self, client):
        prt = make_token(make_user('student'), expired=True)
        resp = self._post(client, prt.token)
        assert resp.status_code == 410
        assert resp.get_json()['error']['code'] == 'TOKEN_EXPIRED'

    def test_expired_token_leaves_password_untouched(self, client):
        user = make_user('student')
        old = user.password
        prt = make_token(user, expired=True)
        self._post(client, prt.token)
        db.session.expire_all()
        assert User.query.get(user.id).password == old

    def test_unknown_token(self, client):
        resp = self._post(client, 'inexistente')
        assert resp.status_code == 404
        assert resp.get_json()['error']['code'] == 'TOKEN_NOT_FOUND'

    def test_used_token_cannot_change_password_again(self, client):
        user = make_user('student')
        old = user.password
        prt = make_token(user, used=True)
        assert self._post(client, prt.token).status_code == 410
        db.session.expire_all()
        assert User.query.get(user.id).password == old

    def test_weak_password(self, client):
        prt = make_token(make_user('student'))
        resp = self._post(client, prt.token, new='debil')
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'WEAK_PASSWORD'

    # Regression (fixed): password_reset_service.consume_token logs action 'password_set_via_token',
    # which UserHistoryService.ACTIONS rejects -> every token set-password returns 500 SERVER_ERROR
    # (app/services/password_reset_service.py:240)
    def test_weak_password_does_not_consume_token(self, client):
        prt = make_token(make_user('student'))
        self._post(client, prt.token, new='debil')
        assert self._post(client, prt.token).status_code == 200

    def test_mismatch(self, client):
        prt = make_token(make_user('student'))
        resp = self._post(client, prt.token, confirm='Otra#Clave99')
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'PASSWORD_MISMATCH'

    def test_missing_fields(self, client):
        prt = make_token(make_user('student'))
        header = seed_csrf(client, 'tok')
        resp = client.post(f'/api/v1/auth/reset-password/{prt.token}', json={},
                           headers={'X-CSRFToken': header})
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'VALIDATION_ERROR'

    def test_requires_csrf(self, client):
        prt = make_token(make_user('student'))
        assert self._post(client, prt.token, csrf=False).status_code == 400

    # Regression (fixed): password_reset_service.consume_token logs action 'password_set_via_token',
    # which UserHistoryService.ACTIONS rejects -> every token set-password returns 500 SERVER_ERROR
    # (app/services/password_reset_service.py:240)
    def test_works_for_user_pending_password_change(self, login):
        user = make_user('student', must_change_password=True)
        prt = make_token(user)
        resp = login(user).post(f'/api/v1/auth/reset-password/{prt.token}',
                                json={'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD})
        assert resp.status_code == 200

    # Regression (fixed): password_reset_service.consume_token logs action 'password_set_via_token',
    # which UserHistoryService.ACTIONS rejects -> every token set-password returns 500 SERVER_ERROR
    # (app/services/password_reset_service.py:240)
    def test_records_history(self, client):
        from app.models.user_history import UserHistory
        user = make_user('student')
        prt = make_token(user)
        self._post(client, prt.token)
        assert UserHistory.query.filter_by(user_id=user.id, action='password_set_via_token').count() == 1

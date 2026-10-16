"""Liveness (/health) and readiness (/ready) probes."""

import time
from unittest.mock import patch

import pytest
import redis
from sqlalchemy.exc import OperationalError

from app import db
from app.routes.api import health_api
from tests.integration.auth_support import fake_redis, isolate_globals  # noqa: F401
from tests.support.factories import make_user


def _db_error(*a, **k):
    raise OperationalError('SELECT 1', {}, Exception('connection lost'))


def _stamp(*revisions):
    db.session.execute(db.text('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)'))
    for rev in revisions:
        db.session.execute(db.text('INSERT INTO alembic_version (version_num) VALUES (:r)'), {'r': rev})
    db.session.commit()


@pytest.fixture
def stamped(app):
    """Database stamped exactly at the heads shipped in this image."""
    _stamp(*sorted(health_api.code_migration_heads()))


# ── /health ─────────────────────────────────────────────────────────────────

class TestHealth:
    def test_ok(self, client):
        resp = client.get('/health')
        assert resp.status_code == 200
        assert resp.get_json() == {'status': 'ok', 'db': True}

    def test_anonymous_no_redirect(self, client):
        assert client.get('/health').status_code == 200

    def test_no_session_cookie_needed_or_issued_noise(self, client):
        resp = client.get('/health')
        assert resp.is_json

    def test_503_when_database_raises(self, client):
        with patch.object(db.session, 'execute', side_effect=_db_error):
            resp = client.get('/health')
        assert resp.status_code == 503
        assert resp.get_json() == {'status': 'degraded', 'db': False}

    def test_failure_rolls_back_so_session_stays_usable(self, client):
        with patch.object(db.session, 'execute', side_effect=_db_error), \
                patch.object(db.session, 'rollback', wraps=db.session.rollback) as rb:
            client.get('/health')
        assert rb.called
        assert client.get('/health').status_code == 200

    def test_session_usable_for_orm_after_failure(self, client):
        with patch.object(db.session, 'execute', side_effect=_db_error):
            client.get('/health')
        user = make_user('student')
        db.session.commit()
        assert user.id is not None

    def test_recovers_after_outage(self, client):
        with patch.object(db.session, 'execute', side_effect=_db_error):
            assert client.get('/health').status_code == 503
        assert client.get('/health').status_code == 200

    def test_does_not_expose_internals(self, client):
        with patch.object(db.session, 'execute', side_effect=_db_error):
            raw = client.get('/health').get_data(as_text=True)
        assert 'connection lost' not in raw

    def test_post_not_allowed(self, client):
        assert client.post('/health').status_code in (400, 405)

    def test_idle_expired_session_not_logged_out_by_probe(self, login):
        client = login(make_user('student'))
        with client.raw.session_transaction() as sess:
            sess['last_activity'] = time.time() - 3600
        assert client.get('/health').status_code == 200


# ── /ready ──────────────────────────────────────────────────────────────────

class TestReady:
    def test_sqlite_create_all_has_no_alembic_table_so_not_ready(self, client, fake_redis):
        resp = client.get('/ready')
        assert resp.status_code == 503
        body = resp.get_json()
        assert body['status'] == 'not_ready'
        assert body['db'] is True
        assert body['redis'] is True
        assert body['schema'] is False
        assert body['db_revisions'] is None

    def test_ready_when_everything_matches(self, client, fake_redis, stamped):
        resp = client.get('/ready')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['status'] == 'ready'
        assert body['db'] and body['redis'] and body['schema']
        assert body['db_revisions'] == body['code_heads']

    def test_reports_code_heads(self, client, fake_redis, stamped):
        body = client.get('/ready').get_json()
        assert body['code_heads'] == sorted(health_api.code_migration_heads())
        assert len(body['code_heads']) >= 1

    def test_reports_static_version(self, app, client, fake_redis, stamped):
        app.config['STATIC_VERSION'] = '9.9.9'
        assert client.get('/ready').get_json()['version'] == '9.9.9'

    def test_empty_alembic_table_is_not_ready(self, client, fake_redis, app):
        _stamp()
        resp = client.get('/ready')
        assert resp.status_code == 503
        assert resp.get_json()['schema'] is False
        assert resp.get_json()['db_revisions'] == []

    def test_stale_revision_is_not_ready(self, client, fake_redis, app):
        _stamp('0000_stale')
        resp = client.get('/ready')
        assert resp.status_code == 503
        body = resp.get_json()
        assert body['schema'] is False
        assert body['db_revisions'] == ['0000_stale']

    def test_database_ahead_of_image_is_not_ready(self, client, fake_redis, app):
        _stamp(*sorted(health_api.code_migration_heads()), 'zzzz_future')
        assert client.get('/ready').status_code == 503

    def test_multiple_heads_must_all_be_stamped(self, client, fake_redis, app, monkeypatch):
        monkeypatch.setattr(health_api, 'code_migration_heads', lambda: frozenset({'a1', 'b2'}))
        _stamp('a1')
        assert client.get('/ready').status_code == 503

    def test_multiple_heads_all_stamped_is_ready(self, client, fake_redis, app, monkeypatch):
        monkeypatch.setattr(health_api, 'code_migration_heads', lambda: frozenset({'a1', 'b2'}))
        _stamp('a1', 'b2')
        assert client.get('/ready').status_code == 200

    def test_redis_down_is_not_ready(self, client, stamped, monkeypatch):
        def refuse(*a, **k):
            raise redis.ConnectionError('refused')
        monkeypatch.setattr(redis, 'from_url', refuse)
        resp = client.get('/ready')
        assert resp.status_code == 503
        body = resp.get_json()
        assert body['redis'] is False
        assert body['db'] is True and body['schema'] is True

    def test_redis_ping_failure_is_not_ready(self, client, stamped, monkeypatch):
        class Dead:
            def ping(self):
                raise redis.TimeoutError('slow')
        monkeypatch.setattr(redis, 'from_url', lambda *a, **k: Dead())
        assert client.get('/ready').get_json()['redis'] is False

    def test_redis_ping_falsy_is_not_ready(self, client, stamped, monkeypatch):
        class Odd:
            def ping(self):
                return False
        monkeypatch.setattr(redis, 'from_url', lambda *a, **k: Odd())
        assert client.get('/ready').status_code == 503

    def test_database_down_is_not_ready(self, client, fake_redis):
        with patch.object(db.session, 'execute', side_effect=_db_error):
            resp = client.get('/ready')
        assert resp.status_code == 503
        body = resp.get_json()
        assert body['db'] is False
        assert body['schema'] is False
        assert body['db_revisions'] is None

    def test_database_down_does_not_poison_session(self, client, fake_redis):
        with patch.object(db.session, 'execute', side_effect=_db_error):
            client.get('/ready')
        assert client.get('/health').status_code == 200

    def test_anonymous_reachable(self, client, fake_redis, stamped):
        resp = client.get('/ready')
        assert resp.status_code == 200
        assert resp.is_json

    def test_reachable_with_must_change_password_user(self, login, fake_redis, stamped):
        client = login(make_user('student', must_change_password=True))
        resp = client.get('/ready')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'ready'

    def test_reachable_with_expired_session(self, login, fake_redis, stamped):
        client = login(make_user('student'))
        with client.raw.session_transaction() as sess:
            sess['last_activity'] = time.time() - 3600
        assert client.get('/ready').status_code == 200

    def test_does_not_leak_secrets(self, app, client, fake_redis, stamped):
        raw = client.get('/ready').get_data(as_text=True)
        assert app.config['SECRET_KEY'] not in raw
        assert 'redis://' not in raw

    def test_not_ready_body_never_has_exception_text(self, client, monkeypatch):
        def refuse(*a, **k):
            raise redis.ConnectionError('secret-host:6379 refused')
        monkeypatch.setattr(redis, 'from_url', refuse)
        assert 'secret-host' not in client.get('/ready').get_data(as_text=True)

    def test_post_not_allowed(self, client):
        assert client.post('/ready').status_code in (400, 405)

    def test_code_migration_heads_is_cached_frozenset(self):
        first = health_api.code_migration_heads()
        assert isinstance(first, frozenset)
        assert health_api.code_migration_heads() is first

    def test_redis_url_comes_from_config(self, app, client, stamped, monkeypatch):
        seen = {}

        def spy(url, **kwargs):
            seen['url'] = url
            raise redis.ConnectionError('x')
        monkeypatch.setattr(redis, 'from_url', spy)
        app.config['REDIS_URL'] = 'redis://cache.test:6379/3'
        client.get('/ready')
        assert seen['url'] == 'redis://cache.test:6379/3'

    def test_redis_probe_uses_short_timeouts(self, client, stamped, monkeypatch):
        seen = {}

        def spy(url, **kwargs):
            seen.update(kwargs)
            raise redis.ConnectionError('x')
        monkeypatch.setattr(redis, 'from_url', spy)
        client.get('/ready')
        assert seen['socket_connect_timeout'] <= 2 and seen['socket_timeout'] <= 2

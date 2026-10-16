"""Unit tests for app/utils/rate_limit.py and app/utils/session_tracker.py (fakeredis)."""

import logging

import fakeredis
import pytest
import redis as redis_lib

from app.utils import rate_limit as rl
from app.utils import session_tracker as st


@pytest.fixture
def fake_redis(monkeypatch):
    """One shared in-memory Redis for every client the modules build."""
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setattr(redis_lib, 'from_url', lambda *a, **kw: fakeredis.FakeRedis(server=server, decode_responses=True))
    monkeypatch.setattr(rl, '_circuit_open_until', 0.0)
    monkeypatch.setattr(st, '_circuit_open_until', 0.0)
    return client


@pytest.fixture
def broken_redis(monkeypatch):
    calls = {'n': 0}

    def boom(*a, **kw):
        calls['n'] += 1
        raise redis_lib.ConnectionError('down')

    monkeypatch.setattr(redis_lib, 'from_url', boom)
    monkeypatch.setattr(rl, '_circuit_open_until', 0.0)
    monkeypatch.setattr(st, '_circuit_open_until', 0.0)
    return calls


# --- pure helpers -----------------------------------------------------------

def test_digest_stable_and_32_hex():
    d = rl._username_digest('alice')
    assert d == rl._username_digest('alice') and len(d) == 32
    int(d, 16)


@pytest.mark.parametrize('variant', ['ALICE', '  alice  ', 'Alice\n'])
def test_digest_case_and_whitespace_insensitive(variant):
    assert rl._username_digest(variant) == rl._username_digest('alice')


def test_digest_differs_per_user():
    assert rl._username_digest('a') != rl._username_digest('b')


@pytest.mark.parametrize('v', ['', None])
def test_digest_empty_or_none_does_not_raise(v):
    assert rl._username_digest(v) == rl._username_digest('')


def test_digest_does_not_contain_username():
    assert 'alice' not in rl._user_key('alice')
    assert rl._user_key('alice').startswith('siiap:loginfail:u:')
    assert rl._block_key('alice').startswith('siiap:loginfail:ub:')


def test_ip_key_unknown_fallback():
    assert rl._ip_key('') == 'siiap:loginfail:ip:unknown'
    assert rl._ip_key('1.2.3.4') == 'siiap:loginfail:ip:1.2.3.4'


def test_setting_defaults(app):
    assert rl._setting('LOGIN_THROTTLE_USER_MAX') == 5
    assert rl._setting('LOGIN_THROTTLE_USER_WINDOW') == 900
    assert rl._setting('LOGIN_THROTTLE_IP_MAX') == 200
    assert rl._setting('LOGIN_THROTTLE_IP_WINDOW') == 300


def test_setting_from_config(app):
    app.config['LOGIN_THROTTLE_USER_MAX'] = 2
    assert rl._setting('LOGIN_THROTTLE_USER_MAX') == 2


def test_setting_from_env(app, monkeypatch):
    monkeypatch.setenv('LOGIN_THROTTLE_USER_MAX', '9')
    assert rl._setting('LOGIN_THROTTLE_USER_MAX') == 9


def test_setting_config_beats_env(app, monkeypatch):
    monkeypatch.setenv('LOGIN_THROTTLE_USER_MAX', '9')
    app.config['LOGIN_THROTTLE_USER_MAX'] = 3
    assert rl._setting('LOGIN_THROTTLE_USER_MAX') == 3


@pytest.mark.parametrize('bad', ['abc', '0', '-4', '', 0, -1])
def test_setting_invalid_falls_back(app, bad):
    app.config['LOGIN_THROTTLE_USER_MAX'] = bad
    assert rl._setting('LOGIN_THROTTLE_USER_MAX') == 5


def test_setting_no_app_context(monkeypatch):
    monkeypatch.delenv('LOGIN_THROTTLE_USER_MAX', raising=False)
    assert rl._setting('LOGIN_THROTTLE_USER_MAX') == 5
    monkeypatch.setenv('LOGIN_THROTTLE_USER_MAX', '7')
    assert rl._setting('LOGIN_THROTTLE_USER_MAX') == 7


def test_user_delays_default(app):
    assert rl._user_delays() == (60, 300, 900)


@pytest.mark.parametrize('raw,expected', [
    ('10,20,30', (10, 20, 30)),
    (' 10 , 20 ', (10, 20)),
    ([5, 6], (5, 6)),
    ((7,), (7,)),
    ('10,,20', (10, 20)),
    ('10,-5,20', (10, 20)),
    ('abc', (60, 300, 900)),
    ('', (60, 300, 900)),
    ('0,0', (60, 300, 900)),
    ('1,x', (60, 300, 900)),
])
def test_user_delays_parsing(app, raw, expected):
    app.config['LOGIN_THROTTLE_USER_DELAYS'] = raw
    assert rl._user_delays() == expected


def test_user_delays_from_env(app, monkeypatch):
    monkeypatch.setenv('LOGIN_THROTTLE_USER_DELAYS', '1,2')
    assert rl._user_delays() == (1, 2)


def test_client_ip_uses_remote_addr_not_forwarded_header(app):
    with app.test_request_context('/', environ_base={'REMOTE_ADDR': '10.1.2.3'},
                                  headers={'X-Forwarded-For': '6.6.6.6'}):
        assert rl.client_ip() == '10.1.2.3'


def test_client_ip_unknown_when_missing(app):
    with app.test_request_context('/', environ_base={'REMOTE_ADDR': ''}):
        assert rl.client_ip() == 'unknown'


# --- register_login_attempt -------------------------------------------------

def test_first_attempts_allowed_up_to_max(app, fake_redis):
    for _ in range(5):
        assert rl.register_login_attempt('alice', '1.1.1.1') is None


def test_sixth_attempt_blocked_with_first_rung(app, fake_redis):
    for _ in range(5):
        rl.register_login_attempt('alice', '1.1.1.1')
    v = rl.register_login_attempt('alice', '1.1.1.1')
    assert v == rl.ThrottleVerdict(scope='username', retry_after=60)
    assert 0 < fake_redis.ttl(rl._block_key('alice')) <= 60


def test_attempts_during_penalty_not_counted_or_rearmed(app, fake_redis):
    for _ in range(6):
        rl.register_login_attempt('alice', '1.1.1.1')
    count_before = int(fake_redis.get(rl._user_key('alice')))
    v = rl.register_login_attempt('alice', '1.1.1.1')
    assert v.scope == 'username' and 1 <= v.retry_after <= 60
    assert int(fake_redis.get(rl._user_key('alice'))) == count_before


def test_escalation_ladder_and_cap(app, fake_redis):
    for _ in range(5):
        rl.register_login_attempt('alice', '1.1.1.1')
    seen = []
    for _ in range(5):
        v = rl.register_login_attempt('alice', '1.1.1.1')
        seen.append(v.retry_after)
        fake_redis.delete(rl._block_key('alice'))  # simulate the delay elapsing
    assert seen == [60, 300, 900, 900, 900]


def test_custom_limits(app, fake_redis):
    app.config['LOGIN_THROTTLE_USER_MAX'] = 1
    app.config['LOGIN_THROTTLE_USER_DELAYS'] = '7,8'
    assert rl.register_login_attempt('bob', 'ip') is None
    assert rl.register_login_attempt('bob', 'ip').retry_after == 7
    fake_redis.delete(rl._block_key('bob'))
    assert rl.register_login_attempt('bob', 'ip').retry_after == 8


def test_users_are_isolated(app, fake_redis):
    for _ in range(6):
        rl.register_login_attempt('alice', '1.1.1.1')
    assert rl.register_login_attempt('bob', '1.1.1.1') is None


def test_username_case_variants_share_budget(app, fake_redis):
    for name in ['Alice', 'ALICE', 'alice', ' alice ', 'aLiCe']:
        assert rl.register_login_attempt(name, 'ip') is None
    assert rl.register_login_attempt('alice', 'ip') is not None


def test_counter_has_ttl_window(app, fake_redis):
    rl.register_login_attempt('alice', '1.1.1.1')
    assert 0 < fake_redis.ttl(rl._user_key('alice')) <= 900


def test_counter_without_ttl_is_repaired(app, fake_redis):
    fake_redis.set(rl._user_key('alice'), 1)  # no TTL
    rl.register_login_attempt('alice', '1.1.1.1')
    assert fake_redis.ttl(rl._user_key('alice')) > 0


def test_ip_counter_without_ttl_is_repaired(app, fake_redis):
    fake_redis.set(rl._ip_key('9.9.9.9'), 1)
    rl.register_login_attempt('alice', '9.9.9.9')
    assert fake_redis.ttl(rl._ip_key('9.9.9.9')) > 0


def test_ip_scope_never_blocks_but_warns(app, fake_redis, caplog):
    app.config['LOGIN_THROTTLE_IP_MAX'] = 3
    app.config['LOGIN_THROTTLE_USER_MAX'] = 1000
    with caplog.at_level(logging.WARNING, logger=rl.logger.name):
        results = [rl.register_login_attempt(f'user{i}', '5.5.5.5') for i in range(7)]
    assert all(r is None for r in results)
    warnings = [r for r in caplog.records if 'fuerza bruta' in r.getMessage()]
    assert len(warnings) == 2  # at counts 3 and 6


def test_clear_login_failures_resets(app, fake_redis):
    for _ in range(6):
        rl.register_login_attempt('alice', '1.1.1.1')
    rl.clear_login_failures('alice')
    assert fake_redis.exists(rl._user_key('alice')) == 0
    assert fake_redis.exists(rl._block_key('alice')) == 0
    assert rl.register_login_attempt('alice', '1.1.1.1') is None


def test_clear_keeps_ip_counter(app, fake_redis):
    rl.register_login_attempt('alice', '3.3.3.3')
    rl.clear_login_failures('alice')
    assert fake_redis.exists(rl._ip_key('3.3.3.3')) == 1


def test_no_plain_username_in_any_redis_key(app, fake_redis):
    rl.register_login_attempt('secret.user@example.org', '1.1.1.1')
    assert not any('secret' in k for k in fake_redis.keys('*'))


# --- fail open / circuit breaker -------------------------------------------

def test_redis_down_fails_open(app, broken_redis):
    assert rl.register_login_attempt('alice', 'ip') is None


def test_redis_down_opens_circuit_and_skips_connection(app, broken_redis):
    rl.register_login_attempt('alice', 'ip')
    assert broken_redis['n'] == 1 and rl._circuit_open_until > 0
    for _ in range(5):
        assert rl.register_login_attempt('alice', 'ip') is None
    assert broken_redis['n'] == 1  # breaker short-circuited the rest


def test_clear_never_raises_when_down(app, broken_redis):
    rl.clear_login_failures('alice')


def test_error_during_pipeline_fails_open(app, monkeypatch):
    class Bad:
        def ttl(self, *_):
            raise RuntimeError('boom')
    monkeypatch.setattr(rl, '_circuit_open_until', 0.0)
    monkeypatch.setattr(rl, '_get_client', lambda: Bad())
    assert rl.register_login_attempt('a', 'ip') is None
    assert rl._circuit_open_until > 0
    monkeypatch.setattr(rl, '_circuit_open_until', 0.0)


def test_get_client_raises_while_circuit_open(app, monkeypatch):
    import time
    monkeypatch.setattr(rl, '_circuit_open_until', time.monotonic() + 100)
    with pytest.raises(redis_lib.ConnectionError):
        rl._get_client()


def test_breaker_own_error_does_not_rearm(app, monkeypatch):
    monkeypatch.setattr(rl, '_circuit_open_until', 0.0)
    rl._handle_error(redis_lib.ConnectionError('Redis circuit breaker open'), 'ctx')
    assert rl._circuit_open_until == 0.0


def test_success_resets_open_circuit(app, fake_redis, monkeypatch):
    monkeypatch.setattr(rl, '_circuit_open_until', 0.0)
    rl.register_login_attempt('a', 'ip')
    assert rl._circuit_open_until == 0.0


# --- session_tracker --------------------------------------------------------

def test_track_and_count_users(app, fake_redis):
    st.track_user_session(1)
    st.track_user_session(2)
    st.track_user_session(1)
    assert st.get_online_users_count() == 2
    assert sorted(st.get_online_users()) == [1, 2]


def test_track_sets_ttl(app, fake_redis):
    st.track_user_session(5)
    assert 0 < fake_redis.ttl('siiap:online:5') <= st.SESSION_TTL


def test_track_renews_ttl(app, fake_redis):
    fake_redis.setex('siiap:online:5', 10, '1')
    st.track_user_session(5)
    assert fake_redis.ttl('siiap:online:5') > 10


def test_online_users_ignores_non_numeric_keys(app, fake_redis):
    fake_redis.set('siiap:online:abc', '1')
    st.track_user_session(3)
    assert st.get_online_users() == [3]


def test_online_users_ignores_other_namespaces(app, fake_redis):
    fake_redis.set('siiap:other:1', '1')
    assert st.get_online_users_count() == 0


def test_online_empty(app, fake_redis):
    assert st.get_online_users() == [] and st.get_online_users_count() == 0


def test_tracker_redis_down_degrades(app, broken_redis):
    st.track_user_session(1)
    assert st.get_online_users_count() == 0
    assert st.get_online_users() == []
    assert broken_redis['n'] == 1  # breaker armed by the first failure


def test_tracker_get_client_raises_while_open(app, monkeypatch):
    import time
    monkeypatch.setattr(st, '_circuit_open_until', time.monotonic() + 100)
    with pytest.raises(redis_lib.ConnectionError):
        st._get_client()


def test_tracker_generic_exception_opens_circuit(app, monkeypatch):
    class Bad:
        def setex(self, *a):
            raise ValueError('x')
    monkeypatch.setattr(st, '_circuit_open_until', 0.0)
    monkeypatch.setattr(st, '_get_client', lambda: Bad())
    st.track_user_session(1)
    assert st._circuit_open_until > 0
    monkeypatch.setattr(st, '_circuit_open_until', 0.0)

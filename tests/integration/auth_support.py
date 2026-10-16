"""
Fixtures and helpers shared by the auth / session / error-handler tests.

Import the fixtures by name into a test module (pytest only discovers them
there or in a conftest):

    from tests.integration.auth_support import fake_redis, isolate_globals  # noqa: F401
"""

import fakeredis
import pytest
import redis

from app import db
from app.models.log import Log
from app.models.password_reset_token import PasswordResetToken
from app.services import password_reset_service as prs
from app.services import auth_audit_service
from app.utils import rate_limit
from tests.support.factories import make_user

LOGIN_URL = '/api/v1/auth/login'
GOOD_PASSWORD = 'Test1234!'
NEW_PASSWORD = 'Nueva#Clave9'


@pytest.fixture
def fake_redis(monkeypatch):
    """Replace every `redis.from_url` with a client on one in-memory server."""
    server = fakeredis.FakeServer()

    def _from_url(url, **kwargs):
        return fakeredis.FakeRedis(server=server, decode_responses=kwargs.get('decode_responses', False))

    monkeypatch.setattr(redis, 'from_url', _from_url)
    monkeypatch.setattr(rate_limit, '_circuit_open_until', 0.0)
    return fakeredis.FakeRedis(server=server, decode_responses=True)


@pytest.fixture(autouse=True)
def isolate_globals(monkeypatch):
    """Process-wide state that would leak between tests."""
    monkeypatch.setattr(rate_limit, '_circuit_open_until', 0.0)
    auth_audit_service._failure_windows.clear()
    yield
    auth_audit_service._failure_windows.clear()


def post_login(client, username, password, **kwargs):
    return client.post(LOGIN_URL, json={'username': username, 'password': password}, **kwargs)


def login_via_api(client, user, password=GOOD_PASSWORD):
    """Real login through the endpoint; returns (response, csrf headers)."""
    resp = post_login(client, user.username, password)
    assert resp.status_code == 200, resp.get_json()
    return resp, {'X-CSRFToken': resp.get_json()['data']['csrf_token']}


def make_token(user, *, purpose='set_password', used=False, expired=False):
    from datetime import timedelta
    from app.utils.datetime_utils import now_local
    prt = prs.generate_token(user.id, purpose=purpose)
    if expired:
        prt.expires_at = now_local() - timedelta(minutes=1)
    if used:
        prt.used_at = now_local()
    db.session.commit()
    return prt


def audit_rows(action=None):
    q = Log.query
    if action:
        q = q.filter_by(action=action)
    return q.order_by(Log.id).all()


def assert_envelope(body, *, code=None):
    assert set(body) >= {'data', 'error', 'meta'}
    if code:
        assert body['error']['code'] == code


def ensure_permission(codename):
    """Get or create a synthetic Permission row (see grant_codename for why)."""
    from app.models.permission import Permission

    perm = Permission.query.filter_by(codename=codename).first()
    if perm is None:
        parts = codename.split('.')
        perm = Permission(codename, codename, parts[0], parts[1], '.'.join(parts[2:]) or 'action')
        db.session.add(perm)
        db.session.flush()
    return perm


def grant_codename(role_name, *codenames):
    """Grant synthetic permissions to a role.

    tests.support.factories.grant() currently fails because Permission.__init__
    does not accept `is_active`; build the rows here until that is fixed.
    """
    from app.models.permission import Permission
    from app.models.role_permission import RolePermission
    from tests.support.factories import get_or_create_role

    role = get_or_create_role(role_name)
    for codename in codenames:
        perm = ensure_permission(codename)
        if not RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first():
            db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.session.commit()

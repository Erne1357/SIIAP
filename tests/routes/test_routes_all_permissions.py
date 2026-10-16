"""Step 4 — render smoke: a postgraduate_admin holding EVERY codename found in
the AST scan GETs every page and every GET API route.

Pass 1 uses dummy ids (404 is fine). Pass 2 substitutes ids of a minimal real
dataset so the page handlers actually reach their templates. Anything >= 500
(or an exception escaping the app) is a bug.
"""

import uuid

import pytest

from app import db
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from tests.support.factories import get_or_create_role, make_user
from tests.routes import _helpers as h
from tests.routes.conftest import client_for

GET_PARAMS = h.case_params('all_permissions', only=lambda id_, m, *_: m == 'GET')

# GET /admin/emails/login redirects to Microsoft (no network here) and the
# callback talks to MS Graph; both are exercised with ms_graph patched below.
MS_ROUTES = {'GET /admin/emails/login', 'GET /admin/emails/callback'}


@pytest.fixture(scope='module')
def admin_id(routes_app):
    with routes_app.app_context():
        # Own bulk grant: tests.support.factories.get_or_create_permission passes
        # `is_active=` to Permission.__init__, which does not accept it.
        role = get_or_create_role('postgraduate_admin')
        for codename in h.all_codenames():
            resource, perm_type, action = codename.split('.')
            perm = Permission(codename, codename, resource, perm_type, action)
            db.session.add(perm)
            db.session.flush()
            db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        admin = make_user('postgraduate_admin')
        db.session.commit()
        return admin.id


@pytest.fixture(autouse=True)
def _no_ms_graph(monkeypatch):
    import app.routes.pages.admin.email_pages as ep
    monkeypatch.setattr(ep, 'build_auth_url', lambda *a, **k: 'http://ms.invalid/auth', raising=False)
    monkeypatch.setattr(ep, 'process_auth_code', lambda *a, **k: {'error': 'x', 'error_description': 'patched'}, raising=False)
    monkeypatch.setattr(ep, 'read_account_info', lambda *a, **k: None, raising=False)


def _real_url(rule, ds):
    subs = {
        'program_id': ds['program_id'], 'slug': ds['program_slug'], 'period_id': ds['period_id'],
        'user_program_id': ds['user_program_id'],
        'user_uuid': ds['applicant_uuid'], 'student_uuid': ds['applicant_uuid'],
    }
    from werkzeug.routing import Rule  # noqa: F401  (rule is a string here)
    url = rule
    import re
    def repl(m):
        name = m.group(2)
        if name in subs:
            return str(subs[name])
        conv = m.group(1) or 'default'
        if conv == 'int':
            return '1'
        if conv == 'uuid':
            return h.DUMMY_UUID
        return 'x'
    return re.sub(r'<(?:(\w+):)?(\w+)>', repl, url)


def _get(app, admin_id, url):
    client = client_for(app, admin_id)
    return client.get(url)


@pytest.mark.parametrize('id_,method,url,rule,is_api', GET_PARAMS)
def test_all_permissions_dummy_ids_never_500(routes_app, admin_id, id_, method, url, rule, is_api):
    resp = _get(routes_app, admin_id, url)
    if id_ == 'GET /ready':          # 503 is the documented answer without Redis
        assert resp.status_code in (200, 503)
        return
    if id_ == 'GET /api/admin/worker/schedules':
        # Regression (fixed): a non-redis broker (memory:// here) used to raise a
        # 500; it is now a controlled 503 with the Spanish envelope.
        assert resp.status_code == 503
        assert resp.get_json()['error'] is not None
        return
    assert resp.status_code < 500, (resp.status_code, resp.get_data(as_text=True)[:300])
    assert resp.status_code != 401


@pytest.mark.parametrize('id_,method,url,rule,is_api', [
    p for p in h.case_params('all_permissions_real', only=lambda id_, m, *_: m == 'GET')
    if '<' in p.values[3] and not p.values[3].startswith('/static')
])
def test_all_permissions_real_ids_never_500(routes_app, admin_id, dataset, id_, method, url, rule, is_api):
    resp = _get(routes_app, admin_id, _real_url(rule, dataset))
    assert resp.status_code < 500, (resp.status_code, resp.get_data(as_text=True)[:300])
    assert resp.status_code != 401


def test_real_dataset_pages_render_200(routes_app, admin_id, dataset):
    """Spot check that the real-id pages are actually reachable, not 404/redirect everywhere."""
    for path in (f"/programs/{dataset['program_slug']}", '/user/dashboard', '/admin/settings/users'):
        resp = _get(routes_app, admin_id, path)
        assert resp.status_code == 200, (path, resp.status_code)

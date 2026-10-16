"""Step 3 — authenticated users of every role with ZERO grants.

Every protected route must refuse them (API: 403/404 JSON envelope; pages: the
403 handler's redirect, or 403/404). The only routes that may answer otherwise
are the explicit LOGIN_ONLY allow-list (self-service endpoints that need a
session and nothing else); those must still never 500.
"""

import pytest

from tests.support.factories import ROLE_NAMES
from tests.routes import _helpers as h
from tests.routes.conftest import client_for

MUTATING = {'POST', 'PUT', 'PATCH', 'DELETE'}
# archives_api still answers with the pre-envelope {"ok": false, "error": ...} shape.
LEGACY_ENVELOPE_PREFIXES = ('/api/v1/archives',)
PARAMS = [p for p in h.case_params('zero_grants') if p.values[0] not in h.PUBLIC]


def test_login_only_allow_list_is_real():
    ids = {p.values[0] for p in PARAMS}
    assert h.LOGIN_ONLY <= ids, sorted(h.LOGIN_ONLY - ids)


@pytest.mark.parametrize('role', ROLE_NAMES)
@pytest.mark.parametrize('id_,method,url,rule,is_api', PARAMS)
def test_zero_grant_user_is_refused(routes_app, role_users, role, id_, method, url, rule, is_api):
    client = client_for(routes_app, role_users[role])
    kw = {'json': {}} if method in MUTATING and is_api else {}
    resp = getattr(client, method.lower())(url, **kw)
    assert resp.status_code < 500, (resp.status_code, resp.get_data(as_text=True)[:300])
    assert resp.status_code != 401, 'valid session was treated as anonymous'

    if id_ in h.LOGIN_ONLY:
        return

    if is_api:
        assert resp.status_code in (403, 404), (resp.status_code, resp.get_data(as_text=True)[:200])
        body = resp.get_json()
        assert body is not None
        if rule.startswith(LEGACY_ENVELOPE_PREFIXES):
            assert body.get('ok') is False or body.get('data') is None, body
        else:
            assert body['data'] is None
            assert body['error']['code'] in ('FORBIDDEN', 'NOT_FOUND')
    else:
        assert resp.status_code in (302, 303, 403, 404), resp.status_code
        if resp.status_code in (302, 303):
            location = resp.headers.get('Location') or ''
            assert location and location != 'None', 'redirect without a usable Location'
            assert not location.split('?')[0].endswith('/login'), 'authenticated user bounced to login'

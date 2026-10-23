"""Step 2 — anonymous matrix over every (method, rule) in the url_map.

Two anonymous flavours:
  A. no session at all  -> GET /api/* is 401 JSON; any mutating call (API or
     page) is stopped earlier by CSRFProtect with 400 JSON (BAD_REQUEST); page
     GETs 302 -> /login.
  B. session carrying a valid CSRF token but no user -> every non-public API
     mutation reaches the login manager and gets 401 JSON; page mutations
     302 -> /login.
Never 500, never 200 for anything outside the PUBLIC allow-list.
"""

import pytest

from app.utils.csrf import CSRF_HEADER
from tests.routes import _helpers as h
from tests.support.fixtures import seed_csrf

MUTATING = {'POST', 'PUT', 'PATCH', 'DELETE'}
PARAMS = h.case_params('anonymous')
NON_PUBLIC = [p for p in PARAMS if p.values[0] not in h.PUBLIC]
PUBLIC_PARAMS = [p for p in PARAMS if p.values[0] in h.PUBLIC]


def _call(client, method, url, **kw):
    fn = getattr(client, method.lower())
    if method in MUTATING:
        kw.setdefault('json', {})
    return fn(url, **kw)


def _assert_envelope(resp, status, code):
    assert resp.status_code == status, (resp.status_code, resp.get_data(as_text=True)[:200])
    body = resp.get_json()
    assert body is not None and body['data'] is None
    assert body['error']['code'] == code


@pytest.mark.parametrize('id_,method,url,rule,is_api', NON_PUBLIC)
def test_anonymous_without_session_is_rejected(routes_app, id_, method, url, rule, is_api):
    client = routes_app.test_client()
    resp = _call(client, method, url)
    assert resp.status_code != 500
    if method in MUTATING:
        _assert_envelope(resp, 400, 'BAD_REQUEST')            # CSRFProtect fires first
    elif is_api:
        _assert_envelope(resp, 401, 'UNAUTHORIZED')
    else:
        assert resp.status_code in (302, 303), resp.status_code
        assert resp.headers['Location'].split('?')[0].endswith('/login')


@pytest.mark.parametrize('id_,method,url,rule,is_api', [p for p in NON_PUBLIC if p.values[4] and p.values[1] in MUTATING])
def test_anonymous_with_csrf_token_gets_401(routes_app, id_, method, url, rule, is_api):
    client = routes_app.test_client()
    header = seed_csrf(client, 'anon-csrf')
    resp = _call(client, method, url, headers={CSRF_HEADER: header})
    _assert_envelope(resp, 401, 'UNAUTHORIZED')


@pytest.mark.parametrize('id_,method,url,rule,is_api', [p for p in NON_PUBLIC if not p.values[4] and p.values[1] in MUTATING])
def test_anonymous_page_mutations_redirect_to_login(routes_app, id_, method, url, rule, is_api):
    client = routes_app.test_client()
    header = seed_csrf(client, 'anon-csrf')
    resp = _call(client, method, url, headers={CSRF_HEADER: header})
    assert resp.status_code in (302, 303)
    assert resp.headers['Location'].split('?')[0].endswith('/login')


# Statuses an anonymous caller may legitimately get from each public route.
PUBLIC_EXPECT = {
    'GET /login': {200},
    'GET /register': {200},
    'POST /register': {200, 302, 400},                       # empty form: re-rendered / rejected
    'GET /reset-password/<token>': {200, 302, 404},
    'GET /health': {200},
    'GET /ready': {200, 503},                                # 503 when Redis/DB unreachable (as in tests)
    'GET /static/<path:filename>': {200, 404},
    'POST /api/v1/auth/login': {400, 401, 422},              # empty credentials, never 200
    'POST /api/v1/auth/reset-password/<token>': {400},       # CSRF guard: no session token
    'GET /api/v1/auth/reset-password/<token>/info': {404},   # unknown token
}


def test_public_expectations_cover_the_allow_list():
    assert set(PUBLIC_EXPECT) == set(h.PUBLIC)


@pytest.mark.parametrize('id_,method,url,rule,is_api', PUBLIC_PARAMS)
def test_public_routes_behave(routes_app, id_, method, url, rule, is_api):
    resp = _call(routes_app.test_client(), method, url)
    assert resp.status_code in PUBLIC_EXPECT[id_], (resp.status_code, resp.get_data(as_text=True)[:200])
    if id_ == 'POST /api/v1/auth/login':
        assert resp.get_json()['error'] is not None

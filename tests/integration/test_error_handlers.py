"""Global error handlers: JSON envelope for /api/*, Spanish HTML / redirects for pages."""

import pytest

from app import db
from tests.integration.auth_routes import register_test_routes
from tests.integration.auth_support import fake_redis, grant_codename, isolate_globals  # noqa: F401
from tests.support.factories import make_user

XHR = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture
def app(app):
    return register_test_routes(app)


def _flashes(client):
    raw = client.raw if hasattr(client, 'raw') else client
    with raw.session_transaction() as sess:
        return [list(f) for f in sess.get('_flashes', [])]


def _assert_envelope(body):
    assert set(body) >= {'data', 'error', 'meta'}
    assert body['data'] is None
    assert body['error']['code'] and body['error']['message']


# ── 404 ─────────────────────────────────────────────────────────────────────

class TestNotFound:
    def test_api_json_envelope(self, client):
        resp = client.get('/api/v1/no-existe')
        assert resp.status_code == 404
        assert resp.is_json
        body = resp.get_json()
        _assert_envelope(body)
        assert body['error']['code'] == 'NOT_FOUND'
        assert body['error']['message'] == 'Recurso no encontrado.'
        assert body['flash'] == [{'level': 'danger', 'message': 'Recurso no encontrado.'}]

    def test_api_message_is_generic_not_werkzeug_description(self, client):
        body = client.get('/api/v1/no-existe').get_data(as_text=True)
        assert 'requested URL was not found' not in body

    def test_page_renders_spanish_html(self, client):
        resp = client.get('/no-existe')
        assert resp.status_code == 404
        assert resp.content_type.startswith('text/html')
        html = resp.get_data(as_text=True)
        assert 'Página no encontrada' in html

    def test_xhr_on_page_path_gets_json(self, client):
        resp = client.get('/no-existe', headers=XHR)
        assert resp.status_code == 404 and resp.is_json

    def test_json_request_on_page_path_gets_json(self, client):
        resp = client.get('/no-existe', content_type='application/json')
        assert resp.status_code == 404 and resp.is_json

    def test_api_abort_404(self, client):
        resp = client.get('/api/v1/_t/abort/404')
        assert resp.status_code == 404
        assert resp.get_json()['error']['code'] == 'NOT_FOUND'

    def test_authenticated_api_404(self, login):
        resp = login(make_user('student')).get('/api/v1/no-existe')
        assert resp.status_code == 404 and resp.get_json()['error']['code'] == 'NOT_FOUND'

    def test_api_404_wrong_method_on_unknown_path(self, login):
        resp = login(make_user('student')).post('/api/v1/no-existe')
        assert resp.status_code == 404


# ── 403 ─────────────────────────────────────────────────────────────────────

class TestForbidden:
    def test_api_json_envelope(self, client):
        resp = client.get('/api/v1/_t/abort/403')
        assert resp.status_code == 403
        body = resp.get_json()
        _assert_envelope(body)
        assert body['error']['code'] == 'FORBIDDEN'
        assert body['error']['message'] == 'No tienes permiso para acceder a este recurso.'
        assert body['flash'][0]['level'] == 'danger'

    def test_page_redirects_to_referrer_with_flash(self, client):
        resp = client.get('/_t/abort/403', headers={'Referer': 'http://localhost/previa'})
        assert resp.status_code == 302
        assert resp.headers['Location'] == 'http://localhost/previa'
        assert ['danger', 'No tienes permiso para acceder a esta página.'] in _flashes(client)

    def test_page_without_referrer_goes_to_index(self, client):
        resp = client.get('/_t/abort/403')
        assert resp.status_code == 302
        assert resp.headers['Location'] in ('/', 'http://localhost/')

    def test_page_referrer_equal_to_current_url_goes_to_index(self, client):
        resp = client.get('/_t/abort/403', headers={'Referer': 'http://localhost/_t/abort/403'})
        assert resp.headers['Location'] in ('/', 'http://localhost/')

    def test_page_post_redirects_with_303(self, client):
        resp = client.post('/_t/abort/403', headers={'Referer': 'http://localhost/previa'})
        assert resp.status_code == 303

    def test_xhr_on_page_path_gets_json(self, client):
        resp = client.get('/_t/abort/403', headers=XHR)
        assert resp.status_code == 403 and resp.get_json()['error']['code'] == 'FORBIDDEN'

    def test_permission_required_api_without_permission(self, login):
        resp = login(make_user('student')).get('/api/v1/_t/perm')
        assert resp.status_code == 403
        body = resp.get_json()
        assert body['error']['code'] == 'FORBIDDEN'
        assert body['error']['message'] == 'No tienes permiso para realizar esta acción.'

    def test_permission_required_page_without_permission_redirects(self, login):
        client = login(make_user('student'))
        resp = client.get('/_t/perm', headers={'Referer': 'http://localhost/previa'})
        assert resp.status_code == 302
        assert resp.headers['Location'] == 'http://localhost/previa'

    def test_permission_required_with_permission_passes(self, login):
        user = make_user('student')
        grant_codename('student', 't.api.secret')
        assert login(user).get('/api/v1/_t/perm').status_code == 200

    def test_permission_is_per_codename(self, login):
        user = make_user('student')
        grant_codename('student', 't.page.secret')
        assert login(user).get('/api/v1/_t/perm').status_code == 403


# ── 400 ─────────────────────────────────────────────────────────────────────

class TestBadRequest:
    def test_api_json_envelope(self, client):
        resp = client.get('/api/v1/_t/abort/400')
        assert resp.status_code == 400
        body = resp.get_json()
        _assert_envelope(body)
        assert body['error']['code'] == 'BAD_REQUEST'
        assert body['flash'][0]['level'] == 'danger'

    def test_json_request_on_page_path(self, client):
        resp = client.post('/_t/abort/400', json={})
        assert resp.status_code == 400 and resp.is_json

    def test_xhr_on_page_path(self, client):
        resp = client.get('/_t/abort/400', headers=XHR)
        assert resp.status_code == 400 and resp.is_json

    def test_page_with_referrer_redirects_back(self, client):
        resp = client.get('/_t/abort/400', headers={'Referer': 'http://localhost/previa'})
        assert resp.status_code == 302
        assert resp.headers['Location'] == 'http://localhost/previa'

    def test_page_post_redirects_with_303(self, client):
        resp = client.post('/_t/abort/400', headers={'Referer': 'http://localhost/previa'})
        assert resp.status_code == 303

    def test_page_flash_uses_error_description(self, client):
        client.get('/_t/abort/400', headers={'Referer': 'http://localhost/previa'})
        flashes = _flashes(client)
        assert flashes and flashes[0][0] == 'danger'

    # Regression (fixed): bad_request handler does redirect(request.referrer) with referrer None (form
    # POST without Referer) -> 'Location: None' (the literal string) instead of a safe fallback
    # (app/__init__.py bad_request: use url_for('index') when referrer is missing)
    def test_page_without_referrer_has_sane_location(self, client):
        resp = client.post('/_t/abort/400')
        assert resp.headers['Location'] in ('/', 'http://localhost/')

    # Regression (fixed): bad_request handler flashes werkzeug's English e.description to page users
    # ('The browser (or proxy) sent a request...'), violating the Spanish-UI rule (app/__init__.py
    # bad_request)
    def test_page_flash_is_spanish(self, client):
        client.get('/_t/abort/400', headers={'Referer': 'http://localhost/previa'})
        message = _flashes(client)[0][1]
        assert 'browser' not in message.lower()

    def test_malformed_json_body_on_api(self, login):
        client = login(make_user('student'))
        resp = client.post('/api/v1/_t/echo', data='{x', content_type='application/json')
        assert resp.status_code == 200  # route ignores the body; handler must not choke


# ── 401 ─────────────────────────────────────────────────────────────────────

class TestUnauthorized:
    def test_login_required_api_is_json(self, client):
        resp = client.get('/api/v1/auth/me')
        assert resp.status_code == 401 and resp.is_json
        assert resp.get_json()['error']['code'] == 'UNAUTHORIZED'

    def test_login_required_page_redirects(self, client):
        resp = client.get('/_t/page')
        assert resp.status_code == 302 and resp.headers['Location'].endswith('/login')

    def test_permission_required_anonymous_is_401(self, client):
        assert client.get('/api/v1/_t/perm').status_code == 401

    # Regression (fixed): abort(401) from permission_required has no errorhandler(401); API callers
    # get Werkzeug's HTML page, so response.json() breaks. Add a 401 handler returning the
    # UNAUTHORIZED envelope (app/__init__.py / app/utils/permissions.py:~80)
    def test_permission_required_anonymous_api_is_json_envelope(self, client):
        resp = client.get('/api/v1/_t/perm')
        assert resp.is_json
        assert resp.get_json()['error']['code'] == 'UNAUTHORIZED'

    # Regression (fixed): abort(401) on a page has no handler: anonymous visitors of a permission-only
    # page get Werkzeug's English HTML instead of a redirect to /login
    def test_permission_required_anonymous_page_redirects_to_login(self, client):
        resp = client.get('/_t/perm')
        assert resp.status_code == 302


# ── 405 / 413 ───────────────────────────────────────────────────────────────

class TestMethodAndSize:
    def test_405_status_on_api(self, login):
        client = login(make_user('student'))
        assert client.post('/api/v1/auth/me').status_code == 405

    # Regression (fixed): no errorhandler(405): /api/* callers receive Werkzeug's HTML instead of the
    # JSON envelope that 400/403/404 already use
    def test_405_api_is_json_envelope(self, login):
        resp = login(make_user('student')).post('/api/v1/auth/me')
        assert resp.is_json
        assert resp.get_json()['error']['code'] == 'METHOD_NOT_ALLOWED'

    def test_405_sets_allow_header(self, login):
        resp = login(make_user('student')).post('/api/v1/auth/me')
        assert 'GET' in resp.headers['Allow']

    def test_413_status_on_api(self, login):
        client = login(make_user('student'))
        resp = client.post('/api/v1/_t/big', data=b'x' * (6 * 1024 * 1024),
                           content_type='application/octet-stream')
        assert resp.status_code == 413

    # Regression (fixed): no errorhandler(413): an oversized upload to /api/* returns Werkzeug's HTML,
    # so the frontend cannot show a Spanish 'archivo demasiado grande' message from the envelope
    def test_413_api_is_json_envelope(self, login):
        client = login(make_user('student'))
        resp = client.post('/api/v1/_t/big', data=b'x' * (6 * 1024 * 1024),
                           content_type='application/octet-stream')
        assert resp.is_json
        assert resp.get_json()['error']['code']

    def test_under_limit_is_accepted(self, login):
        client = login(make_user('student'))
        resp = client.post('/api/v1/_t/big', data=b'x' * 1024, content_type='application/octet-stream')
        assert resp.status_code == 200


# ── 500 ─────────────────────────────────────────────────────────────────────

class TestServerError:
    def test_page_exception_renders_spanish_500(self, client):
        resp = client.get('/_t/boom')
        assert resp.status_code == 500
        assert resp.content_type.startswith('text/html')
        assert 'Algo salió mal del lado del servidor' in resp.get_data(as_text=True)

    def test_page_500_does_not_leak_traceback(self, client):
        body = client.get('/_t/boom').get_data(as_text=True)
        assert 'ZeroDivisionError' not in body and 'Traceback' not in body
        assert 'division by zero' not in body

    def test_abort_500_renders_page(self, client):
        resp = client.get('/_t/abort/500')
        assert resp.status_code == 500
        assert 'Algo salió mal' in resp.get_data(as_text=True)

    def test_api_exception_status_is_500(self, client):
        assert client.get('/api/v1/_t/boom').status_code == 500

    # Regression (fixed): the 500 handler always renders 500.html, even for /api/*, so a failing XHR
    # gets HTML where every other error returns the JSON envelope (app/__init__.py
    # internal_server_error)
    def test_api_exception_is_json_envelope(self, client):
        resp = client.get('/api/v1/_t/boom')
        assert resp.is_json
        body = resp.get_json()
        assert body['error']['code'] == 'SERVER_ERROR'
        assert 'division' not in resp.get_data(as_text=True)

    # Regression (fixed): same as above for abort(500) on /api/*
    def test_api_abort_500_is_json_envelope(self, client):
        assert client.get('/api/v1/_t/abort/500').is_json

    # Regression (fixed): same as above for XHR on page paths
    def test_xhr_page_500_is_json(self, client):
        assert client.get('/_t/boom', headers=XHR).is_json

    def test_app_keeps_serving_after_500(self, client):
        client.get('/_t/boom')
        assert client.get('/health').status_code == 200

    def test_db_session_usable_after_500(self, login):
        client = login(make_user('student'))
        client.get('/_t/boom')
        assert client.get('/api/v1/auth/me').status_code == 200

    def test_authenticated_500_page(self, login):
        client = login(make_user('student'))
        assert client.get('/_t/boom').status_code == 500

    def test_500_in_api_does_not_expose_other_users(self, login):
        client = login(make_user('student', username='ana'))
        assert 'ana' not in client.get('/api/v1/_t/boom').get_data(as_text=True)


# ── cross-cutting ───────────────────────────────────────────────────────────

class TestCrossCutting:
    @pytest.mark.parametrize('code,error_code', [(400, 'BAD_REQUEST'), (403, 'FORBIDDEN'), (404, 'NOT_FOUND')])
    def test_api_error_codes_share_one_envelope(self, client, code, error_code):
        body = client.get(f'/api/v1/_t/abort/{code}').get_json()
        assert set(body) >= {'data', 'error', 'meta', 'flash'}
        assert body['error']['code'] == error_code
        assert body['meta'] == {}

    @pytest.mark.parametrize('code,word', [(403, 'permiso'), (404, 'recurso')])
    def test_api_error_messages_are_spanish(self, client, code, word):
        message = client.get(f'/api/v1/_t/abort/{code}').get_json()['error']['message']
        assert word in message.lower()

    def test_error_response_content_type_json(self, client):
        assert client.get('/api/v1/_t/abort/404').headers['Content-Type'].startswith('application/json')

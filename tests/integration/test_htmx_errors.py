"""htmx requests never get a redirect or a full error page; non-htmx is unchanged."""

import json
import time

import pytest

from tests.integration.auth_routes import register_test_routes
from tests.integration.auth_support import fake_redis, grant_codename, isolate_globals  # noqa: F401
from tests.support.factories import make_user

HX = {'HX-Request': 'true'}


@pytest.fixture
def app(app):
    from app.services.errors import ConflictError, DomainError

    def raise_domain():
        raise DomainError('Regla de negocio incumplida.')

    def raise_conflict():
        raise ConflictError('Ya existe.')

    app.add_url_rule('/_t/domain', 't_domain', raise_domain, methods=['GET', 'POST'])
    app.add_url_rule('/_t/conflict', 't_conflict', raise_conflict, methods=['GET', 'POST'])
    return register_test_routes(app)


def _flash_event(resp):
    """The siiap:flash payload carried by HX-Trigger."""
    return json.loads(resp.headers['HX-Trigger'])['siiap:flash']


def _assert_swap_nothing_with_flash(resp, status, level='danger'):
    assert resp.status_code == status
    assert resp.headers['HX-Reswap'] == 'none'
    assert 'Location' not in resp.headers
    assert resp.get_data() == b''
    event = _flash_event(resp)
    assert event['level'] == level and event['message']
    return event


class TestHtmxErrorMatrix:
    def test_401_redirects_with_hx_redirect_not_302(self, client):
        resp = client.get('/_t/page', headers=HX)
        assert resp.status_code == 401
        assert resp.headers['HX-Redirect'].endswith('/login')
        assert 'Location' not in resp.headers

    def test_403_swaps_nothing_and_flashes(self, login):
        resp = login(make_user('student')).get('/_t/perm', headers=HX)
        event = _assert_swap_nothing_with_flash(resp, 403)
        assert event['message'] == 'No tienes permiso para acceder a este recurso.'

    def test_403_post(self, login):
        resp = login(make_user('student')).post('/_t/abort/403', headers=HX)
        _assert_swap_nothing_with_flash(resp, 403)

    def test_404_swaps_nothing_and_flashes(self, client):
        resp = client.get('/no-existe', headers=HX)
        event = _assert_swap_nothing_with_flash(resp, 404)
        assert event['message'] == 'Recurso no encontrado.'

    def test_400_uses_spanish_message(self, client):
        resp = client.get('/_t/abort/400', headers=HX)
        event = _assert_swap_nothing_with_flash(resp, 400)
        assert event['message'] == 'La solicitud no es válida.'

    def test_csrf_failure_is_400_flash(self, login):
        client = login(make_user('student'))
        resp = client.raw.post('/_t/form', headers=HX)
        event = _assert_swap_nothing_with_flash(resp, 400)
        assert 'Token CSRF' in event['message']

    def test_domain_error_keeps_status_and_level(self, client):
        resp = client.get('/_t/domain', headers=HX)
        event = _assert_swap_nothing_with_flash(resp, 400, level='warning')
        assert event['message'] == 'Regla de negocio incumplida.'

    def test_conflict_error_status(self, client):
        resp = client.get('/_t/conflict', headers=HX)
        assert resp.status_code == 409
        assert resp.headers['HX-Reswap'] == 'none'

    def test_500_swaps_nothing_and_flashes_generic_message(self, client):
        resp = client.get('/_t/boom', headers=HX)
        event = _assert_swap_nothing_with_flash(resp, 500)
        assert 'division' not in resp.headers['HX-Trigger']
        assert event['message'] == 'Ocurrió un error interno. Intenta de nuevo más tarde.'

    def test_405_keeps_allow_header(self, client):
        resp = client.post('/_t/page', headers=HX)
        assert resp.status_code == 405
        assert resp.headers['HX-Reswap'] == 'none'
        assert 'GET' in resp.headers['Allow']

    def test_header_is_latin1_safe(self, client):
        resp = client.get('/_t/domain', headers=HX)
        resp.headers['HX-Trigger'].encode('latin-1')

    def test_hx_request_false_is_not_htmx(self, client):
        resp = client.get('/no-existe', headers={'HX-Request': 'false'})
        assert resp.status_code == 404
        assert 'HX-Trigger' not in resp.headers
        assert resp.content_type.startswith('text/html')


class TestSessionTimeout:
    def _expire(self, client):
        with client.raw.session_transaction() as sess:
            sess['last_activity'] = time.time() - 16 * 60

    def test_expired_session_gets_hx_redirect(self, login):
        client = login(make_user('student'))
        self._expire(client)
        resp = client.get('/_t/open', headers=HX)
        assert resp.status_code == 401
        assert resp.headers['HX-Redirect'].endswith('/login')
        assert 'Location' not in resp.headers

    def test_expired_session_without_hx_still_redirects(self, login):
        client = login(make_user('student'))
        self._expire(client)
        resp = client.get('/_t/open')
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/login')
        assert 'HX-Redirect' not in resp.headers

    def test_expired_api_unchanged(self, login):
        client = login(make_user('student'))
        self._expire(client)
        resp = client.get('/api/v1/_t/echo')
        assert resp.status_code == 401
        assert resp.get_json()['error']['code'] == 'SESSION_EXPIRED'


class TestNonHtmxUnchanged:
    def test_401_page_still_302(self, client):
        resp = client.get('/_t/page')
        assert resp.status_code == 302
        assert 'HX-Redirect' not in resp.headers

    def test_403_page_still_redirects(self, login):
        resp = login(make_user('student')).get('/_t/perm')
        assert resp.status_code == 302 and 'HX-Reswap' not in resp.headers

    def test_404_page_still_html(self, client):
        resp = client.get('/no-existe')
        assert resp.status_code == 404 and 'HX-Trigger' not in resp.headers

    def test_500_page_still_html(self, client):
        resp = client.get('/_t/boom')
        assert resp.status_code == 500 and resp.content_type.startswith('text/html')

    def test_domain_error_page_still_303(self, client):
        resp = client.post('/_t/domain', headers={'Referer': 'http://localhost/x'})
        assert resp.status_code in (303, 400)
        assert 'HX-Reswap' not in resp.headers

"""App-level handler for InvalidAdmissionTransition (unguarded state-machine refusals)."""

import pytest

from tests.integration.auth_routes import register_test_routes
from tests.integration.auth_support import fake_redis, isolate_globals  # noqa: F401

EXPECTED = 'No se puede cambiar el estado de admisión de "inscrito" a "en proceso".'


def _raise():
    from app.services.admission_status_service import InvalidAdmissionTransition
    raise InvalidAdmissionTransition('enrolled', 'in_progress')


@pytest.fixture
def app(app):
    register_test_routes(app)
    app.add_url_rule('/api/v1/_t/transition', 't_transition_api', _raise)
    app.add_url_rule('/_t/transition', 't_transition_page', _raise)
    return app


def test_api_route_returns_400_business_error(client):
    resp = client.get('/api/v1/_t/transition')
    assert resp.status_code == 400
    body = resp.get_json()
    assert body['data'] is None
    assert body['error']['code'] == 'BUSINESS_ERROR'
    assert body['error']['message'] == EXPECTED


def test_page_route_redirects_with_flash(client):
    resp = client.get('/_t/transition')
    assert resp.status_code in (302, 303)
    with client.session_transaction() as sess:
        flashed = sess.get('_flashes') or []
    assert any(EXPECTED in msg for _cat, msg in flashed)

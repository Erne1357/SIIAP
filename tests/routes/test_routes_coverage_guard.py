"""Step 6 — fail when a route is added/removed without being classified."""

from tests.routes import _helpers as h
from tests.routes._route_snapshot import KNOWN_ROUTES


def _current(routes_app):
    return {id_ for id_, *_ in h.iter_cases(routes_app)}


def test_no_unclassified_routes(routes_app):
    """Every new (METHOD, rule) must be added to _route_snapshot.KNOWN_ROUTES.

    Doing so is the classification step: unless it is also added to
    _helpers.PUBLIC it is treated as PROTECTED and the anonymous, zero-grant and
    all-permission matrices start covering it automatically.
    """
    current = _current(routes_app)
    new = sorted(current - KNOWN_ROUTES)
    gone = sorted(KNOWN_ROUTES - current)
    assert not new, f'NEW routes not classified (add to KNOWN_ROUTES; to _helpers.PUBLIC if open): {new}'
    assert not gone, f'routes removed; update KNOWN_ROUTES/PUBLIC/LOGIN_ONLY: {gone}'


def test_allow_lists_only_reference_known_routes():
    assert h.PUBLIC <= KNOWN_ROUTES, sorted(h.PUBLIC - KNOWN_ROUTES)
    assert h.LOGIN_ONLY <= KNOWN_ROUTES, sorted(h.LOGIN_ONLY - KNOWN_ROUTES)
    assert not (h.PUBLIC & h.LOGIN_ONLY)


def test_public_set_is_small_and_has_no_data_routes():
    """A public route that is not an auth/health/static one is a red flag."""
    allowed_prefixes = ('GET /login', 'GET /register', 'POST /register', 'GET /reset-password',
                        'GET /health', 'GET /ready', 'GET /static', 'POST /api/v1/auth/')
    stray = [r for r in h.PUBLIC if not r.startswith(allowed_prefixes) and r != 'GET /api/v1/auth/reset-password/<token>/info']
    assert not stray, stray


def test_every_api_route_lives_under_a_known_prefix(routes_app):
    prefixes = ('/api/v1/', '/api/admin/')
    bad = [r.rule for r in routes_app.url_map.iter_rules()
           if r.rule.startswith('/api/') and not r.rule.startswith(prefixes)]
    assert not bad, bad

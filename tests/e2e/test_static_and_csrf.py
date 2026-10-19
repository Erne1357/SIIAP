"""
Flow 7 — static assets carry the STATIC_VERSION cache-buster and load.
Flow 8 — session cookie and CSRF protection on API mutations.
"""

import re
from urllib.parse import parse_qs, urlparse

import pytest

import accounts as acc
from audit import settle

pytestmark = pytest.mark.e2e

#: STATIC_VERSION in docker/docker-compose.e2e.yml; the app's own fallback
#: (app/config.py) is a different literal, so seeing this proves the env wiring.
EXPECTED_VERSION = 'e2e'
FALLBACK_VERSION = '1.0.42081201'

_COLLECT_JS = """() => {
  const abs = (u) => new URL(u, location.href);
  const own = (u) => abs(u).origin === location.origin;
  const css = Array.from(document.querySelectorAll('link[rel=stylesheet][href]')).map(l => l.href);
  const js = Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
  const preload = Array.from(document.querySelectorAll('link[rel=preload][href]')).map(l => l.href);
  return {css: css.filter(own), js: js.filter(own), preload: preload.filter(own)};
}"""


def collect_assets(page):
    found = page.evaluate(_COLLECT_JS)
    return found


PAGES = [
    ('/login', None),
    ('/user/dashboard', acc.APPLICANT),
    ('/programs/', acc.APPLICANT),
    (f'/programs/{acc.PROGRAM_SLUG}', acc.COORDINATOR),
    (f'/programs/admission/{acc.PROGRAM_SLUG}', acc.APPLICANT),
    ('/user/dashboard', acc.POSTGRAD),
]


@pytest.mark.parametrize('path, account', PAGES,
                         ids=[f'{p}-{a.role if a else "anon"}' for p, a in PAGES])
def test_every_stylesheet_and_script_is_versioned_and_loads(page, login_as, path, account):
    if account:
        login_as(account)
    page.goto(path)
    settle(page)
    assets = collect_assets(page)
    own = assets['css'] + assets['js'] + assets['preload']
    assert len(assets['css']) >= 8 and len(assets['js']) >= 3, assets

    problems = []
    for url in own:
        parsed = urlparse(url)
        if not parsed.path.startswith('/static/'):
            problems.append(f'not served from /static/: {url}')
            continue
        version = parse_qs(parsed.query).get('v', [None])[0]
        if version != EXPECTED_VERSION:
            problems.append(f'?v={version!r} instead of {EXPECTED_VERSION!r}: {url}')
            continue
        response = page.request.get(url)
        if response.status != 200:
            problems.append(f'{response.status}: {url}')
        elif not response.body():
            problems.append(f'empty body: {url}')
    assert not problems, '\n'.join(problems)


# Regression (fixed): ES-module imports are not cache-busted. static/js/auth/login.js does `import
# { api } from "../api/http.js"`, so the browser requests /static/js/api/http.js with no
# ?v=<STATIC_VERSION>; nginx serves /static/ as immutable for a year, so after a release the login
# page keeps running the previous http.js
def test_every_script_and_stylesheet_request_carries_the_version(page, login_as):
    """Network-level: also catches assets that are loaded indirectly (module imports, @import)."""
    unversioned = set()

    def on_request(request):
        parsed = urlparse(request.url)
        if (parsed.path.startswith('/static/') and parsed.path.endswith(('.js', '.css'))
                and parse_qs(parsed.query).get('v') != [EXPECTED_VERSION]):
            unversioned.add(parsed.path)

    page.on('request', on_request)
    page.goto('/login')
    settle(page)
    login_as(acc.APPLICANT)
    for path in ('/user/dashboard', f'/programs/admission/{acc.PROGRAM_SLUG}', '/programs/'):
        page.goto(path)
        settle(page)
    assert not unversioned, f'requested without ?v={EXPECTED_VERSION}: {sorted(unversioned)}'


def test_static_version_fallback_is_not_in_use(page):
    page.goto('/login')
    assert FALLBACK_VERSION not in page.content()


def test_stylesheets_are_actually_applied(page):
    """200 is not enough: the sheets must parse (a broken @import or MIME would not)."""
    page.goto('/login')
    settle(page)
    own_sheets = page.evaluate(
        """() => Array.from(document.styleSheets)
              .filter(s => s.href && new URL(s.href).origin === location.origin)
              .map(s => { try { return s.cssRules.length; } catch (e) { return -1; } })""")
    assert own_sheets and all(n > 0 for n in own_sheets), own_sheets
    # A token from _tokens.css resolves, proving the design system core loaded first.
    primary = page.evaluate(
        "() => getComputedStyle(document.documentElement).getPropertyValue('--color-brand-primary')")
    assert primary.strip(), 'design token --color-brand-primary is not defined'


# ── CSRF ─────────────────────────────────────────────────────────────────────

MUTATION = '/api/v1/notifications/mark-all-read'


def csrf_token(page):
    return page.locator('meta[name="csrf-token"]').get_attribute('content')


def test_mutation_without_csrf_header_is_rejected(page, login_as, diag):
    diag.allow_status(400, r'/api/')
    login_as(acc.APPLICANT)
    page.goto('/user/dashboard')

    missing = page.request.post(MUTATION)
    assert missing.status == 400
    assert 'CSRF' in missing.json()['error']['message']

    wrong = page.request.post(MUTATION, headers={'X-CSRFToken': 'token-falso'})
    assert wrong.status == 400
    assert 'inválido' in wrong.json()['error']['message']

    # CSRFProtect guards each routed (path, method), so every URL here must
    # really accept the method; an unrouted one is a plain 405.
    some_uuid = '00000000-0000-7000-8000-000000000000'
    for method, url in (('put', f'/api/v1/archives/{some_uuid}'),
                        ('patch', f'/api/v1/archives/{some_uuid}'),
                        ('delete', f'/api/v1/submissions/{some_uuid}')):
        r = getattr(page.request, method)(url)
        assert r.status == 400, f'{method.upper()} {url} without CSRF header returned {r.status}'


def test_mutation_with_the_pages_csrf_token_is_accepted(page, login_as):
    login_as(acc.APPLICANT)
    page.goto('/user/dashboard')
    ok = page.request.post(MUTATION, headers={'X-CSRFToken': csrf_token(page)})
    assert ok.status == 200, ok.text()
    assert ok.json().get('error') is None


def test_safe_methods_do_not_need_the_token(page, login_as):
    login_as(acc.APPLICANT)
    page.goto('/user/dashboard')
    assert page.request.get('/api/v1/auth/me').status == 200


def test_mutation_without_a_session_is_rejected_before_anything_else(playwright, base_url):
    api = playwright.request.new_context(base_url=base_url)
    try:
        r = api.post(MUTATION)
        assert r.status == 400
        assert r.json()['error']['code'] == 'BAD_REQUEST'
    finally:
        api.dispose()


def test_token_from_another_session_is_rejected(page, login_as, playwright, base_url, diag):
    """A token is bound to its session: the one of user A does not work for user B."""
    diag.allow_status(400, r'/api/')
    login_as(acc.APPLICANT)
    page.goto('/user/dashboard')
    token_a = csrf_token(page)

    login_as(acc.STUDENT)
    page.goto('/user/dashboard')
    r = page.request.post(MUTATION, headers={'X-CSRFToken': token_a})
    assert r.status == 400


def test_session_cookie_is_httponly_and_samesite(page, login_as):
    login_as(acc.APPLICANT)
    page.goto('/user/dashboard')
    cookie = next(c for c in page.context.cookies() if c['name'] == 'siiap_session')
    assert cookie['httpOnly'] is True
    assert cookie['sameSite'] == 'Lax'
    assert not re.search(r'document\.cookie.*siiap_session',
                         page.evaluate('() => document.cookie')), 'session cookie readable from JS'
    assert 'siiap_session' not in page.evaluate('() => document.cookie')

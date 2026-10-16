"""
Browser E2E fixtures. Self-contained on purpose: the e2e container runs with
`--confcutdir=tests/e2e`, so the root tests/conftest.py (which imports the Flask
app) is never loaded here. Only pytest + playwright are available.

What this file provides
  * `diag`       (autouse) records, per test, every browser console error, uncaught
                 page exception, same-origin 5xx, same-origin failed request and
                 same-origin 4xx on a sub-resource / XHR. A test that finishes green
                 but produced any of them is turned into a FAILURE (see the
                 makereport hook). Tests that provoke an error on purpose declare it
                 with `diag.allow_console(...)` / `diag.allow_status(...)`.
  * `login_as`   fast login: signs in through /api/v1/auth/login once per account
                 per session and reuses the session cookie. The real UI login form
                 is exercised separately in test_auth.py.
"""

import re
from urllib.parse import urlparse

import pytest

from accounts import PASSWORD  # noqa: F401  (re-exported for convenience)

#: Console messages that are the browser's own echo of a failed request. The
#: network side is asserted separately (status / requestfailed), so counting
#: the echo again would only duplicate every finding.
_RESOURCE_ECHO = re.compile(r'^Failed to load resource')

#: Third-party hosts the pages load from (fonts, Bootstrap, Socket.IO client).
#: A request failure here is the sandbox's connectivity, not an app defect, so
#: it is ignored. A *script error* that follows is not: it still fails the test.
THIRD_PARTY_HOSTS = (
    'fonts.googleapis.com', 'fonts.gstatic.com', 'cdn.jsdelivr.net', 'cdn.socket.io',
)


def _describe(response) -> str:
    """One line per response, with the content of any session cookie it sets."""
    import base64, json, zlib
    try:
        headers = response.all_headers()
    except Exception:
        headers = response.headers
    cookie = headers.get('set-cookie', '')
    shown = ''
    if 'siiap_session=' in cookie:
        raw = cookie.split('siiap_session=', 1)[1].split(';', 1)[0]
        try:
            body = raw[1:] if raw.startswith('.') else raw
            body = body.split('.')[0]
            body += '=' * (-len(body) % 4)
            data = base64.urlsafe_b64decode(body)
            data = zlib.decompress(data) if raw.startswith('.') else data
            keys = json.loads(data)
            shown = ' SET-COOKIE keys=' + ','.join(sorted(k for k in keys if not k.startswith('_csrf')))
            if '_flashes' in keys:
                shown += f' flashes={keys["_flashes"]}'
            if 'last_activity' in keys:
                import time
                shown += f' age={time.time() - keys["last_activity"]:.0f}s'
        except Exception as exc:  # debugging aid only
            shown = f' SET-COOKIE (undecodable: {exc})'
        if 'Expires=Thu, 01 Jan 1970' in cookie:
            shown += ' EXPIRED'
    try:
        sent = response.request.all_headers().get('cookie', '')
    except Exception:
        sent = '?'
    sent_note = ' [no cookie sent]' if not sent else f' [cookie sent len={len(sent)}]'
    return f'{response.status} {response.request.method} {response.url}{sent_note}{shown}'


class Diagnostics:
    """Collects browser-side problems for one test."""

    def __init__(self, origin: str):
        self.origin = origin
        self._host = urlparse(origin).netloc
        self.console_errors: list[str] = []
        self.page_errors: list[str] = []
        self.server_errors: list[str] = []
        self.client_errors: list[str] = []
        self.failed_requests: list[str] = []
        self.trace: list[str] = []
        #: fetch/XHR requests currently in flight (Socket.IO transport excluded);
        #: audit.settle() waits for this to drain instead of for `networkidle`,
        #: which never settles while Socket.IO long-polls.
        self.pending: set = set()
        self._console_allow: list[re.Pattern] = []
        self._status_allow: list[tuple[int, re.Pattern]] = []

    # -- declared, expected noise ------------------------------------------
    def allow_console(self, pattern: str) -> None:
        """Do not fail on console errors whose text matches `pattern` (regex)."""
        self._console_allow.append(re.compile(pattern))

    def allow_status(self, status: int, url_pattern: str = '.*') -> None:
        """Do not fail on `status` for same-origin URLs matching `url_pattern`."""
        self._status_allow.append((status, re.compile(url_pattern)))

    # -- wiring ------------------------------------------------------------
    def same_origin(self, url: str) -> bool:
        return urlparse(url).netloc == self._host

    def attach(self, page) -> None:
        page._e2e_diag = self
        page.on('request', self._on_request)
        page.on('requestfinished', lambda r: self.pending.discard(r))
        page.on('console', self._on_console)
        page.on('pageerror', lambda exc: self.page_errors.append(str(exc)))
        page.on('response', self._on_response)
        page.on('requestfailed', self._on_request_failed)

    def _on_request(self, request) -> None:
        if request.resource_type in ('fetch', 'xhr') and '/socket.io/' not in request.url:
            self.pending.add(request)

    def _on_console(self, msg) -> None:
        if msg.type != 'error':
            return
        text = msg.text
        if _RESOURCE_ECHO.match(text):
            return
        if any(p.search(text) for p in self._console_allow):
            return
        self.console_errors.append(f'{text} ({msg.location.get("url", "?")})')

    def _on_response(self, response) -> None:
        url = response.url
        if self.same_origin(url) and response.request.resource_type in ('document', 'fetch', 'xhr'):
            self.trace.append(_describe(response))
        if not self.same_origin(url):
            return
        status = response.status
        if any(s == status and p.search(url) for s, p in self._status_allow):
            return
        if status >= 500:
            self.server_errors.append(f'{status} {response.request.method} {url}')
        elif status >= 400 and response.request.resource_type != 'document':
            # A deliberate navigation to a 404/403 page is the *document*; a 4xx
            # on an asset or a fetch/XHR is a broken reference or a missing grant.
            self.client_errors.append(f'{status} {response.request.method} {url}')

    def _on_request_failed(self, request) -> None:
        self.pending.discard(request)
        if not self.same_origin(request.url):
            return
        failure = request.failure or ''
        # Navigations/XHRs cancelled by the next navigation are not failures.
        if 'ERR_ABORTED' in failure or 'NS_BINDING_ABORTED' in failure:
            return
        self.failed_requests.append(f'{request.method} {request.url} -> {failure}')

    # -- verdict -----------------------------------------------------------
    def problems(self) -> list[str]:
        out = []
        out += [f'console.error: {m}' for m in self.console_errors]
        out += [f'uncaught exception: {m}' for m in self.page_errors]
        out += [f'server error: {m}' for m in self.server_errors]
        out += [f'4xx on sub-resource/XHR: {m}' for m in self.client_errors]
        out += [f'request failed: {m}' for m in self.failed_requests]
        return out


# ── pytest-playwright configuration ──────────────────────────────────────────

@pytest.fixture(scope='session')
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        'locale': 'es-MX',
        'timezone_id': 'America/Ciudad_Juarez',
        'viewport': {'width': 1280, 'height': 800},
    }


@pytest.fixture
def diag(request, page, base_url):
    """Per-test browser diagnostics, attached to the test's `page`."""
    page.set_default_timeout(10_000)
    page.set_default_navigation_timeout(30_000)
    d = Diagnostics(base_url)
    d.attach(page)
    request.node._e2e_diag = d
    return d


@pytest.fixture(autouse=True)
def _auto_diag(diag):
    """Every test gets diagnostics, whether or not it asks for them."""
    return diag


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """
    Turn browser problems into a failure of the *call* phase (not a teardown
    error), so xfail(strict=True) markers keep working on tests that document a
    known app defect through its console output.
    """
    result = yield
    d = getattr(item, '_e2e_diag', None)
    problems = d.problems() if d else []
    if problems:
        raise AssertionError(
            'The assertions passed but the browser reported problems:\n  - '
            + '\n  - '.join(problems)
        )
    return result


# ── Authentication helpers ───────────────────────────────────────────────────

@pytest.fixture(scope='session')
def _session_cookies():
    """username -> cookies, filled lazily by `login_as`."""
    return {}


@pytest.fixture
def login_as(page, base_url, playwright, _session_cookies):
    """
    `login_as(account)` leaves `page`'s context signed in as `account`.

    Each call uses a throwaway API context so cookies of different accounts never
    mix; the cookies are cached per account for the rest of the session and
    verified against /api/v1/auth/me before the test starts (a cached session that
    no longer authenticates is minted again, once).
    """
    def _mint(account):
        api = playwright.request.new_context(base_url=base_url)
        try:
            response = api.post(
                '/api/v1/auth/login',
                data={'username': account.username, 'password': account.password},
            )
            assert response.ok, f'login of {account.username} failed: {response.status} {response.text()}'
            return api.storage_state()['cookies']
        finally:
            api.dispose()

    def _login(account):
        from audit import settle  # local import: audit.py is a sibling module

        # Leave the current document first (letting its XHRs finish): in-flight
        # requests would otherwise answer after the swap and write the previous
        # user's cookie back into the jar.
        if page.url != 'about:blank':
            settle(page, timeout=1500)
            page.goto('about:blank')
        for attempt in (1, 2):
            cookies = _session_cookies.get(account.username)
            if cookies is None:
                cookies = _session_cookies[account.username] = _mint(account)
            page.context.clear_cookies()
            page.context.add_cookies(cookies)
            if page.request.get('/api/v1/auth/me').status == 200:
                return account
            _session_cookies.pop(account.username, None)
        raise AssertionError(f'could not establish a session for {account.username}')

    return _login

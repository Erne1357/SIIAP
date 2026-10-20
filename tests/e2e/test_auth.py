"""Flows 2 and 3 — signing in and out, and the forced password change."""

import re
import uuid

import pytest
from playwright.sync_api import expect

import accounts as acc
from audit import settle

pytestmark = pytest.mark.e2e

#: Anchored: the show/hide button is also labelled "Mostrar contraseña".
PASSWORD_LABEL = re.compile(r'^Contraseña')

GENERIC_FAILURE = 'Usuario o contraseña inválidos'


def sign_in(page, account, password=None):
    """Drive the real login form."""
    page.goto('/login')
    # login.js is a deferred module: submitting before it runs would fall back to
    # a native form submit that just reloads /login.
    settle(page)
    page.get_by_label('Usuario').fill(account.username)
    page.get_by_label(PASSWORD_LABEL).fill(password if password is not None else account.password)
    page.get_by_role('button', name='Entrar').click()


# ── Failure paths ────────────────────────────────────────────────────────────

@pytest.mark.parametrize('case, username, password', [
    ('wrong password', acc.APPLICANT_NEW.username, 'Incorrecta-123!'),
    ('unknown user', f'inexistente_{uuid.uuid4().hex[:10]}', 'Incorrecta-123!'),
    ('inactive account, right password', acc.INACTIVE.username, acc.PASSWORD),
])
def test_failed_login_shows_one_generic_spanish_message(page, diag, case, username, password):
    """The three failures are indistinguishable: no user-existence oracle."""
    # login.js logs the rejected promise with console.error and the browser echoes
    # the 401: both are the expected trace of a failed sign-in.
    diag.allow_console(r'^Login error:')
    diag.allow_status(401, r'/api/v1/auth/login')
    page.goto('/login')
    settle(page)
    page.get_by_label('Usuario').fill(username)
    page.get_by_label(PASSWORD_LABEL).fill(password)
    page.get_by_role('button', name='Entrar').click()

    expect(page.locator('#flash-container')).to_contain_text(GENERIC_FAILURE)
    expect(page).to_have_url(re.compile(r'/login$'))

    alert_text = page.locator('#flash-container').inner_text().lower()
    for leak in ('no existe', 'inactiv', 'desactiv', 'bloquead', 'incorrecta', 'registrad'):
        assert leak not in alert_text, f'{case}: message leaks "{leak}": {alert_text!r}'


def test_failed_login_api_bodies_are_identical_across_causes(playwright, base_url):
    """Same status and body for wrong password, unknown user and disabled account."""
    unknown = f'inexistente_{uuid.uuid4().hex[:10]}'  # fresh name: never throttled
    api = playwright.request.new_context(base_url=base_url)
    try:
        bodies = []
        for username in (acc.APPLICANT_NEW.username, unknown, acc.INACTIVE_API.username):
            r = api.post('/api/v1/auth/login', data={'username': username, 'password': 'Incorrecta-123!'})
            bodies.append((r.status, r.json()))
        assert {s for s, _ in bodies} == {401}
        assert bodies[0][1] == bodies[1][1] == bodies[2][1]
        assert bodies[0][1]['error']['message'] == GENERIC_FAILURE

        # A correct password clears the real user's failure counter (throttle policy).
        ok = api.post('/api/v1/auth/login',
                      data={'username': acc.APPLICANT_NEW.username, 'password': acc.PASSWORD})
        assert ok.status == 200
    finally:
        api.dispose()


def test_empty_form_asks_for_the_missing_field_in_spanish(page):
    page.goto('/login')
    page.get_by_role('button', name='Entrar').click()
    expect(page.locator('#usernameError')).to_be_visible()
    expect(page.locator('#usernameError')).to_have_text(re.compile('Escribe tu nombre de usuario'))
    expect(page.locator('#username')).to_have_attribute('aria-invalid', 'true')
    expect(page.locator('#username')).to_be_focused()

    page.get_by_label('Usuario').fill('alguien')
    page.get_by_role('button', name='Entrar').click()
    expect(page.locator('#passwordError')).to_be_visible()
    expect(page.locator('#password')).to_be_focused()


def test_password_toggle_reveals_and_hides_the_password(page):
    page.goto('/login')
    field = page.locator('#password')
    expect(field).to_have_attribute('type', 'password')
    page.locator('[data-toggle-password="#password"]').click()
    expect(field).to_have_attribute('type', 'text')
    page.locator('[data-toggle-password="#password"]').click()
    expect(field).to_have_attribute('type', 'password')


# ── Success for every role ───────────────────────────────────────────────────

@pytest.mark.parametrize('account', acc.ROLE_ACCOUNTS, ids=lambda a: a.role)
def test_each_role_signs_in_and_lands_on_its_dashboard(page, account):
    sign_in(page, account)
    page.wait_for_url(re.compile(r'/user/dashboard$'))
    settle(page)
    expect(page.locator('html')).to_have_attribute('lang', 'es')
    expect(page).to_have_title('Inicio - SIIAP')
    # The role badge in the sidebar is rendered from the permissions the role
    # holds, so it proves the right permission set reached the template.
    expect(page.locator('#sidebar .user-card')).to_contain_text(account.role_label)
    expect(page.get_by_role('heading', level=1, name='Panel de control')).to_be_attached()
    expect(page.locator('#sidebar').get_by_role('button', name='Cerrar sesión')).to_be_visible()


def test_social_service_gets_the_placeholder_dashboard(page, login_as):
    login_as(acc.SOCIAL)
    page.goto('/user/dashboard')
    expect(page.get_by_text('Tu panel aún no está disponible')).to_be_visible()
    expect(page.get_by_role('link', name='Ir a mi perfil')).to_be_visible()


# ── Logout and protected pages ───────────────────────────────────────────────

def test_logout_returns_to_login_and_protects_pages(page, diag):
    diag.allow_status(401, r'/api/v1/auth/me')
    sign_in(page, acc.APPLICANT)
    page.wait_for_url(re.compile(r'/user/dashboard$'))
    settle(page)

    page.locator('#sidebar').get_by_role('button', name='Cerrar sesión').click()
    page.wait_for_url(re.compile(r'/login$'))
    expect(page.get_by_role('button', name='Entrar')).to_be_visible()

    # The session is gone: a protected page redirects to login with the notice.
    page.goto('/user/dashboard')
    expect(page).to_have_url(re.compile(r'/login$'))
    expect(page.locator('#flash-container')).to_contain_text('Por favor, inicia sesión')

    # ...and so does the API, with the JSON envelope rather than a redirect.
    r = page.request.get('/api/v1/auth/me')
    assert r.status == 401
    assert r.json()['error']['code'] == 'UNAUTHORIZED'


def test_logout_via_get_link_redirects_to_login(page, login_as):
    login_as(acc.STUDENT)
    page.goto('/api/v1/auth/logout')
    expect(page).to_have_url(re.compile(r'/login$'))
    page.goto('/user/dashboard')
    expect(page).to_have_url(re.compile(r'/login$'))


def test_wrong_role_page_is_refused_politely(page, login_as):
    """An applicant opening a coordinator page is bounced back with a Spanish notice."""
    login_as(acc.APPLICANT)
    page.goto('/user/dashboard')
    page.goto('/coordinator/dashboard')
    expect(page.locator('#flash-container')).to_contain_text('No tienes permiso para acceder a esta página.')


# ── Forced password change ───────────────────────────────────────────────────

def _flagged_account(playwright, base_url):
    """First pool account that still has must_change_password (None when all used)."""
    api = playwright.request.new_context(base_url=base_url)
    try:
        for account in acc.FORCED_POOL:
            r = api.post('/api/v1/auth/login',
                         data={'username': account.username, 'password': account.password})
            if r.ok and r.json()['data']['must_change_password']:
                return account
    finally:
        api.dispose()
    return None


@pytest.fixture
def flagged(playwright, base_url):
    account = _flagged_account(playwright, base_url)
    if account is None:
        pytest.skip('every must_change_password account was consumed; re-seed the app '
                    '(docker compose -f docker/docker-compose.e2e.yml up -d --force-recreate app)')
    return account


#: notifications.js:73 reads `data.count` of an unread-count response whose body is
#: the PASSWORD_CHANGE_REQUIRED error (data: null). Tracked by the xfail below.
NOTIFICATION_BADGE_BUG = r'^Error updating notification badge'


# Regression (fixed): static/js/notifications.js:73 (NotificationManager.updateBadge) dereferences
# `data.count` of /api/v1/notifications/unread-count, which answers 403 PASSWORD_CHANGE_REQUIRED
# with data=null while the forced-change modal is up: TypeError in the console on every page load
# of a must_change_password user (same TypeError on the signed-out 404 page)
def test_forced_change_page_has_no_console_errors(page, diag, flagged):
    diag.allow_status(403, r'/api/')
    sign_in(page, flagged)
    page.wait_for_url(re.compile(r'/user/dashboard$'))
    expect(page.get_by_role('dialog', name='Cambio de contraseña requerido')).to_be_visible()
    settle(page)


def test_forced_change_blocks_navigation_and_api(page, diag, flagged):
    diag.allow_status(403, r'/api/')
    diag.allow_console(NOTIFICATION_BADGE_BUG)
    sign_in(page, flagged)
    page.wait_for_url(re.compile(r'/user/dashboard$'))

    dialog = page.get_by_role('dialog', name='Cambio de contraseña requerido')
    expect(dialog).to_be_visible()

    # The modal is static: neither Escape nor a click on the backdrop closes it.
    page.keyboard.press('Escape')
    expect(dialog).to_be_visible()
    page.mouse.click(5, 5)
    expect(dialog).to_be_visible()

    # Typing another URL is bounced back to the page that hosts the modal.
    page.goto('/programs/')
    expect(page).to_have_url(re.compile(r'/user/dashboard$'))
    expect(page.locator('#flash-container')).to_contain_text(
        'Debes cambiar tu contraseña antes de continuar.')

    # The API refuses everything except the password change itself.
    r = page.request.get('/api/v1/notifications')
    assert r.status == 403
    assert r.json()['error']['code'] == 'PASSWORD_CHANGE_REQUIRED'


def test_forced_change_validates_then_unlocks_the_app(page, diag, flagged):
    diag.allow_status(400, r'/api/v1/auth/change-password')
    diag.allow_status(401, r'/api/v1/auth/change-password')
    diag.allow_status(403, r'/api/')
    diag.allow_console(NOTIFICATION_BADGE_BUG)
    sign_in(page, flagged)
    page.wait_for_url(re.compile(r'/user/dashboard$'))
    dialog = page.get_by_role('dialog', name='Cambio de contraseña requerido')
    expect(dialog).to_be_visible()
    submit = dialog.get_by_role('button', name='Cambiar Contraseña')

    # Weak password: the requirements list is shown and the server refuses.
    dialog.locator('#current_password').fill(flagged.password)
    dialog.locator('#new_password').fill('debil')
    dialog.locator('#confirm_password').fill('debil')
    expect(dialog.locator('#password_strength_feedback')).to_contain_text('Requisitos de contraseña')
    submit.click()
    expect(dialog).to_be_visible()

    # A valid new password closes the modal and the flag is cleared.
    dialog.locator('#new_password').fill(acc.NEW_PASSWORD)
    dialog.locator('#confirm_password').fill(acc.NEW_PASSWORD)
    submit.click()
    expect(dialog).to_be_hidden()

    me = page.request.get('/api/v1/auth/me').json()['data']
    assert me['must_change_password'] is False

    page.goto('/programs/')
    expect(page).to_have_url(re.compile(r'/programs/$'))
    expect(page.get_by_role('heading', level=1)).to_be_visible()

    # The new password works from a clean session.
    page.locator('#sidebar').get_by_role('button', name='Cerrar sesión').click()
    page.wait_for_url(re.compile(r'/login$'))
    sign_in(page, flagged, password=acc.NEW_PASSWORD)
    page.wait_for_url(re.compile(r'/user/dashboard$'))
    expect(page.get_by_role('dialog', name='Cambio de contraseña requerido')).to_be_hidden()

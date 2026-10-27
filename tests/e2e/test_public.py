"""Flow 1 — what an anonymous visitor (and a freshly registered applicant) sees."""

import re

import pytest
from playwright.sync_api import expect

import accounts as acc
from audit import audit_page, settle

pytestmark = pytest.mark.e2e

#: Anchored: the show/hide button is also labelled "Mostrar contraseña".
PASSWORD_LABEL = re.compile(r'^Contraseña')


def test_root_redirects_anonymous_visitors_to_login(page):
    response = page.goto('/')
    assert response.status == 200
    expect(page).to_have_url(re.compile(r'/login$'))


def test_login_page_is_spanish_and_labelled(page):
    page.goto('/login')
    settle(page)
    expect(page.locator('html')).to_have_attribute('lang', 'es')
    expect(page).to_have_title('SIIAP – Iniciar Sesión')
    expect(page.get_by_role('heading', name='Iniciar sesión')).to_be_visible()
    expect(page.get_by_label('Usuario')).to_be_visible()
    expect(page.get_by_label(PASSWORD_LABEL)).to_be_visible()
    expect(page.get_by_role('button', name='Entrar')).to_be_enabled()
    expect(page.get_by_role('link', name='Regístrate')).to_be_visible()
    expect(page.get_by_role('link', name='Saltar al contenido principal')).to_be_attached()

    problems, _unnamed = audit_page(page)
    assert not problems, problems


def test_register_page_renders_in_spanish(page):
    page.goto('/register')
    expect(page.locator('html')).to_have_attribute('lang', 'es')
    expect(page.locator('h1')).to_have_count(1)
    expect(page.locator('form')).to_be_visible()


def test_login_page_redirects_authenticated_users_to_dashboard(page, login_as):
    login_as(acc.APPLICANT)
    page.goto('/login')
    expect(page).to_have_url(re.compile(r'/user/dashboard$'))


@pytest.mark.parametrize('path', ['/programs/', f'/programs/{acc.PROGRAM_SLUG}',
                                  '/user/dashboard', '/admin/settings/', '/admin/review/'])
def test_protected_pages_send_anonymous_visitors_to_login_with_spanish_notice(page, path):
    page.goto(path)
    expect(page).to_have_url(re.compile(r'/login$'))
    expect(page.locator('#flash-container')).to_contain_text(
        'Por favor, inicia sesión para acceder a esta página.')


def test_program_catalogue_lists_seeded_programs(page, login_as):
    login_as(acc.APPLICANT_NEW)
    page.goto('/programs/')
    settle(page)
    expect(page.get_by_role('heading', level=1)).to_be_visible()
    expect(page.get_by_text(acc.PROGRAM_NAME).first).to_be_visible()
    expect(page.get_by_text(acc.PROGRAM_NAME_2).first).to_be_visible()


def test_program_page_offers_postularme_to_a_new_applicant(page, login_as):
    login_as(acc.APPLICANT_NEW)
    page.goto(f'/programs/{acc.PROGRAM_SLUG}')
    settle(page)
    expect(page.get_by_role('heading', level=1)).to_contain_text(acc.PROGRAM_NAME)
    cta = page.get_by_role('button', name='Postularme')
    expect(cta).to_be_visible()

    # CLAUDE.md documents that the CTA pulses (siiap-program-cta-pulse) and stops
    # under prefers-reduced-motion. Both halves are asserted: the pulse is what
    # keeps Playwright from considering the button "stable".
    assert page.evaluate(
        "() => getComputedStyle(document.querySelector('.btn-inscription')).animationName"
    ) == 'siiap-program-cta-pulse'
    page.emulate_media(reduced_motion='reduce')
    assert page.evaluate(
        "() => getComputedStyle(document.querySelector('.btn-inscription')).animationName"
    ) == 'none'

    # The call to action opens the enrollment dialog (the admission window is
    # open in the seed). It is cancelled: enrolling would change shared state.
    cta.click()
    dialog = page.locator('#enrollmentModal')
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role('button', name='Sí, postularme')).to_be_visible()
    expect(dialog).to_have_class(re.compile('show'))
    # Bootstrap ignores hide() while the fade-in is still running.
    page.wait_for_timeout(500)
    dialog.get_by_role('button', name='Cancelar').click()
    expect(dialog).to_be_hidden()


def test_program_page_sends_an_enrolled_applicant_to_their_process_instead(page, login_as):
    login_as(acc.APPLICANT)
    page.goto(f'/programs/{acc.PROGRAM_SLUG}')
    settle(page)
    expect(page.get_by_role('button', name='Postularme')).to_have_count(0)
    expect(page.get_by_role('link', name='Ir a mi proceso')).to_be_visible()


def test_program_page_has_no_application_cta_for_staff(page, login_as):
    login_as(acc.COORDINATOR)
    page.goto(f'/programs/{acc.PROGRAM_SLUG}')
    settle(page)
    expect(page.get_by_role('heading', level=1)).to_contain_text(acc.PROGRAM_NAME)
    expect(page.get_by_role('button', name='Postularme')).to_have_count(0)


# Regression (fixed): base.html loads notifications.js and force_password_change.js for anonymous
# visitors, so the 404 page of a signed-out user fires 401s on /api/v1/auth/me,
# /notifications/unread-count, /invitations/my-invitations and notifications.js:73 throws "Cannot
# read properties of null (reading "count")
def test_unknown_page_renders_the_spanish_404(page):
    response = page.goto('/esta-pagina-no-existe')
    assert response.status == 404
    expect(page.locator('html')).to_have_attribute('lang', 'es')
    expect(page).to_have_title(re.compile('404'))
    expect(page.get_by_role('heading', level=1, name='Página no encontrada')).to_be_visible()
    # exact: the header brand link is named "SIIAP — ir al inicio".
    expect(page.get_by_role('link', name='Inicio', exact=True)).to_be_visible()
    settle(page)


def test_unknown_page_content_is_correct_for_anonymous_visitors(page, diag):
    """Same page as above, minus the console assertions that the BUG xfail covers."""
    diag.allow_console(r'.')
    diag.allow_status(401, r'/api/')
    response = page.goto('/esta-pagina-no-existe')
    assert response.status == 404
    expect(page.get_by_role('heading', level=1, name='Página no encontrada')).to_be_visible()


def test_unknown_program_slug_renders_the_spanish_404(page, login_as):
    login_as(acc.APPLICANT)
    response = page.goto('/programs/no-existe-este-programa')
    assert response.status == 404
    expect(page.get_by_role('heading', level=1, name='Página no encontrada')).to_be_visible()


def test_unknown_api_route_answers_with_the_json_envelope_in_spanish(page):
    response = page.request.get('/api/v1/no-existe')
    assert response.status == 404
    body = response.json()
    assert body['data'] is None
    assert body['error']['code'] == 'NOT_FOUND'
    assert body['error']['message'] == 'Recurso no encontrado.'


def test_health_and_readiness_probes(page):
    assert page.request.get('/health').status == 200
    assert page.request.get('/ready').status == 200

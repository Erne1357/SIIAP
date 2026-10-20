"""
Flows 5 and 6 — every sidebar destination of every role loads cleanly, and the
accessibility / responsive smoke checks run on each visited page.

Per page the `diag` fixture already fails the test on console errors, uncaught
exceptions, 5xx and 4xx on sub-resources. On top of that:
  * desktop: html[lang=es], exactly one <h1>, one <main>, skip link, <title>,
    images carry an alt attribute (audit.audit_page)
  * mobile (375px): no horizontal scroll, and the navigation drawer's controls
    are at least 44px tall (CLAUDE.md, WCAG 2.5.5 target size)
"""

from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

import accounts as acc
from audit import audit_page, horizontal_overflow, nav_links, settle, small_targets

pytestmark = pytest.mark.e2e

ROLES = [acc.APPLICANT, acc.STUDENT, acc.COORDINATOR, acc.POSTGRAD, acc.SOCIAL]
ROLE_IDS = [a.role for a in ROLES]

#: Pages every role can open besides the sidebar ones.
EXTRA_PAGES = ['/user/dashboard', '/user/profile', '/programs/', f'/programs/{acc.PROGRAM_SLUG}']


def _path(url):
    parsed = urlparse(url)
    return parsed.path.rstrip('/') or '/'


def visit(page, href, problems, diag=None):
    """Open `href` and record everything wrong with it into `problems`."""
    response = page.goto(href)
    settle(page)
    wanted = _path(href)
    if response is None or response.status >= 400:
        problems.append(f'{href}: HTTP {response.status if response else "no response"}')
        return
    if not _path(page.url).startswith(wanted):
        problems.append(f'{href}: ended on {page.url} (redirected away)')  # deeper paths (index -> /submissions) are fine
        if diag is not None:
            problems.append('   trace:\n     ' + '\n     '.join(diag.trace[-30:]))
        return
    page_problems, _unnamed = audit_page(page)
    problems.extend(f'{href}: {p}' for p in page_problems)


@pytest.mark.parametrize('account', ROLES, ids=ROLE_IDS)
def test_sidebar_destinations_load_cleanly(page, base_url, login_as, account, diag):
    login_as(account)
    page.goto('/user/dashboard')
    settle(page)
    links = nav_links(page, base_url)
    assert len(links) >= 4, f'sidebar for {account.role} has only {links}'

    problems = []
    for href in list(dict.fromkeys(links + EXTRA_PAGES)):
        visit(page, href, problems, diag)
    assert not problems, '\n'.join(problems)


def test_sidebar_is_role_specific(page, base_url, login_as):
    """The permission sets reach the navigation: each role sees only its own links."""
    seen = {}
    for account in (acc.APPLICANT, acc.COORDINATOR, acc.POSTGRAD, acc.SOCIAL):
        login_as(account)
        page.goto('/user/dashboard')
        seen[account.role] = set(nav_links(page, base_url))

    assert '/coordinator/dashboard' not in seen['applicant']
    assert f'/programs/admission/{acc.PROGRAM_SLUG}' in seen['applicant']
    assert '/coordinator/dashboard' in seen['program_admin']
    assert '/admin/settings/academic-periods' not in seen['program_admin']
    assert '/admin/settings/academic-periods' in seen['postgraduate_admin']
    assert '/admin/settings/permissions' in seen['postgraduate_admin']
    assert seen['social_service'] <= seen['postgraduate_admin']
    assert '/coordinator/dashboard' not in seen['social_service']


def test_current_group_arrives_open_with_aria_current_and_breadcrumb(page, login_as):
    """The group of the page being viewed is open server-side and survives outside clicks."""
    login_as(acc.POSTGRAD)
    page.goto('/admin/settings/users')
    settle(page)
    sidebar = page.locator('#sidebar')
    toggle = sidebar.get_by_role('button', name='Configuración')
    expect(toggle).to_have_attribute('aria-expanded', 'true')
    expect(sidebar.get_by_role('link', name='Usuarios')).to_have_attribute('aria-current', 'page')
    page.locator('main').click(position={'x': 5, 'y': 5})
    expect(toggle).to_have_attribute('aria-expanded', 'true')
    crumbs = page.get_by_role('navigation', name='Ruta de navegación')
    expect(crumbs).to_contain_text('Configuración')
    expect(crumbs.locator('[aria-current="page"]')).to_have_text('Usuarios')


def test_header_has_one_logo_and_footer_the_institutional_ones(page, login_as):
    login_as(acc.APPLICANT)
    page.goto('/user/dashboard')
    settle(page)
    assert page.locator('#page-header img').count() == 1
    for alt in ('SEP', 'TecNM', 'ITCJ', 'Posgrado'):
        expect(page.locator('footer').get_by_alt_text(alt)).to_be_visible()


# ── Mobile ───────────────────────────────────────────────────────────────────

@pytest.fixture
def phone(page):
    page.set_viewport_size({'width': 375, 'height': 812})
    return page


#: Roles whose whole sidebar is swept at 375px. The student, coordinator and
#: social-service destinations are subsets of the applicant's and the
#: postgraduate admin's (the desktop sweep above covers each of them in full), so
#: for those three only their own dashboard and the shared pages are measured.
FULL_MOBILE_SWEEP = {'applicant', 'postgraduate_admin'}


@pytest.mark.parametrize('account', ROLES, ids=ROLE_IDS)
def test_no_horizontal_scroll_at_375px(phone, base_url, login_as, account):
    login_as(account)
    phone.goto('/user/dashboard')
    settle(phone)
    if account.role in FULL_MOBILE_SWEEP:
        # The desktop sidebar is hidden on phones; collect destinations from the drawer.
        hrefs = phone.evaluate(
            """() => Array.from(document.querySelectorAll('#mobileSidebar nav a[href]'))
                           .map(a => a.getAttribute('href'))""")
        pages = list(dict.fromkeys(
            [h for h in hrefs if h and not h.startswith(('#', 'mailto:'))] + EXTRA_PAGES))
    else:
        pages = ['/user/dashboard', '/user/profile', '/programs/']
    overflowing = []
    for href in pages:
        phone.goto(href)
        settle(phone, timeout=1200)  # let the page's tables/cards render before measuring
        overflow = horizontal_overflow(phone)
        if overflow:
            overflowing.append(f'{href}: {overflow[0]}')
    assert not overflowing, '\n'.join(overflowing)


def open_drawer(phone):
    phone.get_by_role('button', name='Abrir menú de navegación').click()
    drawer = phone.locator('#mobileSidebar')
    expect(drawer).to_be_visible()
    phone.wait_for_timeout(400)  # offcanvas slide-in transition
    # Expand the collapsed groups so their links are measured too (the group of
    # the current page already arrives open from the server; clicking it would fold it).
    for toggle in drawer.locator('button.dropdown-toggle-custom[aria-expanded="false"]').all():
        toggle.click()
    phone.wait_for_timeout(300)
    return drawer


@pytest.mark.parametrize('account', ROLES, ids=ROLE_IDS)
def test_mobile_drawer_links_meet_the_44px_target(phone, login_as, account):
    login_as(account)
    phone.goto('/user/dashboard')
    settle(phone)
    open_drawer(phone)
    small = small_targets(phone, '#mobileSidebar .nav-link, #mobileSidebar .js-api-logout')
    assert not small, 'controls under 44px in the mobile drawer: ' + '; '.join(small)


# Regression (fixed): the offcanvas close button (#mobileSidebar .btn-close, Bootstrap default) is
# 32x32 px at 375px width; CLAUDE.md requires >= 44px touch targets (.tap-target)
def test_mobile_drawer_close_button_meets_the_44px_target(phone, login_as):
    login_as(acc.APPLICANT)
    phone.goto('/user/dashboard')
    settle(phone)
    open_drawer(phone)
    small = small_targets(phone, '#mobileSidebar .btn-close')
    assert not small, 'close button under 44px: ' + '; '.join(small)


def test_header_controls_meet_the_44px_target_on_mobile(phone, login_as):
    login_as(acc.APPLICANT)
    phone.goto('/user/dashboard')
    settle(phone)
    small = small_targets(phone, '.btn-menu-toggle, .notification-fab, .notification-bell-btn')
    assert not small, 'header controls under 44px: ' + '; '.join(small)


# ── Keyboard focus ───────────────────────────────────────────────────────────

_FOCUS_JS = """() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const s = getComputedStyle(el);
  const outline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0;
  const shadow = s.boxShadow && s.boxShadow !== 'none';
  return {tag: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''), visible: outline || shadow};
}"""


@pytest.mark.parametrize('path, anonymous', [('/login', True), ('/user/dashboard', False)])
def test_first_tab_stops_show_a_visible_focus_indicator(page, login_as, path, anonymous):
    if not anonymous:
        login_as(acc.APPLICANT)
    page.goto(path)
    settle(page)
    page.locator('body').click(position={'x': 1, 'y': 1})
    invisible = []
    for _ in range(8):
        page.keyboard.press('Tab')
        info = page.evaluate(_FOCUS_JS)
        if info and not info['visible']:
            invisible.append(info['tag'])
    assert not invisible, f'focused elements without outline/box-shadow: {invisible}'

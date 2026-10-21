"""Unit tests for app/navigation.py: the menu defined as data."""

import re

import pytest

from app import db
from app.navigation import MENU, Navigation
from tests.routes import _helpers as h
from tests.support.factories import enroll, get_or_create_role, grant, make_program, make_user

ALL_ITEMS = [(g, i) for g in MENU for i in g.items]

# Permission sets per role (synthetic: only the codenames the menu looks at).
APPLICANT = ('programs.api.enroll', 'submissions.api.upload')
STUDENT = ('submissions.api.upload',)
SOCIAL = ('admin_review.page.view',)
COORDINATOR = (
    'coordinator.page.view', 'deliberation.page.view', 'acceptance.page.view',
    'permanence.page.view', 'admin_review.page.view', 'events.page.view',
    'archives.api.list', 'admin_users.page.view', 'admin_emails.api.manage',
    'admin_templates.page.view', 'student_bulk.page.view',
    'curriculum.page.manage', 'teaching.page.my_groups',
)
POSTGRAD = COORDINATOR + (
    'academic_periods.api.create', 'admin_celery.api.manage',
    'permissions.page.manage_roles', 'admin.page.purge',
)


def _user(role_name, codenames):
    user = make_user(role_name)
    grant(get_or_create_role(role_name), *codenames)
    db.session.commit()
    return user


def _nav(app, user, endpoint='pages_user.dashboard'):
    with app.test_request_context():
        return Navigation.for_user(user, endpoint)


def _links(nav):
    return {item.key for group in nav.groups for item in group.items}


def _group_keys(nav):
    return [g.key for g in nav.groups]


# ── Structure ────────────────────────────────────────────────────────────────

def test_groups_follow_the_workflow_order():
    assert [g.key for g in MENU] == [
        'inicio', 'admision', 'permanencia', 'eventos', 'expedientes', 'docencia',
        'configuracion']


def test_keys_are_unique():
    keys = [i.key for _, i in ALL_ITEMS]
    assert len(keys) == len(set(keys))
    assert len({g.key for g in MENU}) == len(MENU)


@pytest.mark.parametrize('group, item', ALL_ITEMS, ids=lambda x: getattr(x, 'key', ''))
def test_every_endpoint_exists_in_the_url_map(app, group, item):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert item.endpoint in endpoints
    for extra in item.active_endpoints:
        assert extra in endpoints, extra
    for prefix in item.active_prefixes:
        assert any(e.startswith(prefix) for e in endpoints), prefix


@pytest.mark.parametrize('group, item', ALL_ITEMS, ids=lambda x: getattr(x, 'key', ''))
def test_permission_codenames_are_well_formed_and_icons_are_bootstrap(group, item):
    for codename in item.any_of + item.all_of:
        assert h.CODENAME_RE.match(codename), codename
    assert re.fullmatch(r'bi-[a-z0-9-]+', item.icon)
    assert re.fullmatch(r'bi-[a-z0-9-]+', group.icon)


@pytest.mark.parametrize('group, item', ALL_ITEMS, ids=lambda x: getattr(x, 'key', ''))
def test_link_is_gated_by_the_permission_its_route_requires(app, group, item):
    """A link must be visible exactly when the click would not 403."""
    view = app.view_functions[item.endpoint]
    views, _ = h.scan_routes()
    module_file = view.__module__.replace('.', '/') + '.py'
    required = {
        p for v in views
        if v['func'] == view.__name__ and v['file'] == module_file
        for p in v['perms']
    }
    if not required:
        pytest.skip('route has no permission decorator (login only)')
    assert required & set(item.any_of + item.all_of), (
        f'{item.endpoint} requires {sorted(required)}')


# ── Visibility per role ──────────────────────────────────────────────────────

def test_applicant_sees_workflow_links_and_nothing_administrative(app):
    user = _user('applicant', APPLICANT)
    enroll(user, make_program(slug='maestria-x'))
    db.session.commit()
    nav = _nav(app, user)
    assert _group_keys(nav) == ['inicio', 'admision', 'eventos']
    assert _links(nav) == {'home', 'profile', 'programs', 'my-admission', 'events'}
    admission = next(i for g in nav.groups for i in g.items if i.key == 'my-admission')
    assert admission.href.endswith('/programs/admission/maestria-x')


def test_applicant_without_a_program_has_no_admission_link(app):
    nav = _nav(app, _user('applicant', APPLICANT))
    assert 'my-admission' not in _links(nav)


def test_student_does_not_get_the_applicant_admission_link(app):
    user = _user('student', STUDENT)
    enroll(user, make_program())
    db.session.commit()
    assert 'my-admission' not in _links(_nav(app, user))


def test_social_service_only_reviews_documents(app):
    nav = _nav(app, _user('social_service', SOCIAL))
    assert _links(nav) == {'home', 'profile', 'programs', 'review', 'events'}


def test_coordinator_sees_staff_groups_but_not_global_settings(app):
    user = _user('program_admin', COORDINATOR)
    make_program(coordinator=user, slug='mi-programa')
    db.session.commit()
    nav = _nav(app, user)
    assert _group_keys(nav) == [
        'inicio', 'admision', 'permanencia', 'eventos', 'expedientes', 'docencia',
        'configuracion']
    links = _links(nav)
    assert {'curriculum', 'my-groups', 'review', 'deliberation', 'acceptance', 'permanence', 'events-admin',
            'students', 'bulk-import', 'files', 'users', 'emails', 'templates',
            'program-config'} <= links
    assert not links & {'periods', 'celery', 'permissions', 'cleanup', 'programs-config'}
    mine = next(i for g in nav.groups for i in g.items if i.key == 'program-config')
    assert mine.href.endswith('/settings/program/mi-programa')


def test_each_settings_link_is_gated_individually(app):
    """Holding one settings permission shows that link only, not the whole menu."""
    nav = _nav(app, _user('program_admin', ('admin_users.page.view',)))
    config = next(g for g in nav.groups if g.key == 'configuracion')
    assert [i.key for i in config.items] == ['users']


def test_postgraduate_admin_sees_everything_and_no_coordinator_program_link(app):
    nav = _nav(app, _user('postgraduate_admin', POSTGRAD))
    links = _links(nav)
    every_key = {i.key for _, i in ALL_ITEMS}
    assert links == every_key - {'my-admission', 'program-config'}


def test_user_without_permissions_gets_only_the_open_links(app):
    nav = _nav(app, make_user('student'))
    assert _links(nav) == {'home', 'profile', 'programs', 'events'}


# ── Active detection ─────────────────────────────────────────────────────────

def _active(nav):
    item = nav.active_item
    return (nav.active_group.key, item.key) if item else None


@pytest.mark.parametrize('endpoint, expected', [
    ('pages_user.dashboard', ('inicio', 'home')),
    ('pages_user.profile', ('inicio', 'profile')),
    ('program.list_programs', ('admision', 'programs')),
    ('program.view_program', ('admision', 'programs')),
    # Regression: the old menu tested `review.` but the endpoint is nested.
    ('pages_admin.pages_review.index', ('admision', 'review')),
    ('pages_admin.pages_review.submission_detail', ('admision', 'review')),
    ('pages_coordinator.deliberation', ('admision', 'deliberation')),
    ('pages_coordinator.acceptance', ('admision', 'acceptance')),
    ('pages_coordinator.permanence', ('permanencia', 'permanence')),
    ('pages_events_public.view_event', ('eventos', 'events')),
    ('pages_admin.pages_events.detail', ('eventos', 'events-admin')),
    ('pages_coordinator.dashboard', ('expedientes', 'students')),
    ('pages_student_record.student_record', ('expedientes', 'students')),
    ('pages_admin.pages_settings.retention', ('configuracion', 'files')),
    ('pages_admin.pages_emails.ms_login', ('configuracion', 'emails')),
    ('pages_admin.pages_settings.permissions_manager', ('configuracion', 'permissions')),
])
def test_active_item_for_endpoint(app, endpoint, expected):
    nav = _nav(app, _user('postgraduate_admin', POSTGRAD), endpoint)
    assert _active(nav) == expected
    assert nav.active_group.current


def test_config_program_highlights_the_programs_entry_not_the_catalog(app):
    """Regression: the old check looked for config_program on the list link."""
    admin = _nav(app, _user('postgraduate_admin', POSTGRAD),
                 'pages_admin.pages_settings.config_program')
    assert _active(admin) == ('configuracion', 'programs-config')

    coord = _user('program_admin', COORDINATOR)
    make_program(coordinator=coord)
    db.session.commit()
    nav = _nav(app, coord, 'pages_admin.pages_settings.config_program')
    assert _active(nav) == ('configuracion', 'program-config')


def test_catalog_page_prefers_the_admission_group_for_admins(app):
    nav = _nav(app, _user('postgraduate_admin', POSTGRAD), 'program.list_programs')
    assert _active(nav) == ('admision', 'programs')
    assert sum(1 for g in nav.groups for i in g.items if i.active) == 1


def test_unknown_endpoint_activates_nothing(app):
    nav = _nav(app, _user('program_admin', COORDINATOR), 'api_users.me')
    assert nav.active_group is None and nav.active_item is None
    assert nav.title is None and nav.breadcrumbs() == []


def test_hidden_item_cannot_be_active(app):
    nav = _nav(app, _user('applicant', APPLICANT), 'pages_admin.pages_settings.users')
    assert nav.active_item is None


# ── Title and breadcrumbs ────────────────────────────────────────────────────

def test_title_and_breadcrumbs_come_from_the_active_item(app):
    with app.test_request_context():
        nav = Navigation.for_user(_user('program_admin', COORDINATOR), 'pages_coordinator.deliberation')
        assert nav.title == 'Deliberación'
        crumbs = nav.breadcrumbs()
    assert [c['label'] for c in crumbs] == ['Inicio', 'Admisión', 'Deliberación']
    assert crumbs[0]['href'] and crumbs[1]['href'] is None and crumbs[2]['href'] is None


def test_breadcrumbs_on_home_is_only_the_page(app):
    with app.test_request_context():
        nav = Navigation.for_user(make_user('student'), 'pages_user.dashboard')
        crumbs = nav.breadcrumbs()
    assert [c['label'] for c in crumbs] == ['Inicio']


def test_breadcrumbs_inicio_group_other_page_links_home(app):
    with app.test_request_context():
        nav = Navigation.for_user(make_user('student'), 'pages_user.profile')
        crumbs = nav.breadcrumbs()
    assert [c['label'] for c in crumbs] == ['Inicio', 'Perfil']
    assert crumbs[0]['href']


def test_breadcrumbs_single_item_group_does_not_repeat_its_label(app):
    with app.test_request_context():
        user = _user('program_admin', ('permanence.page.view',))
        crumbs = Navigation.for_user(user, 'pages_coordinator.permanence').breadcrumbs()
    assert [c['label'] for c in crumbs] == ['Inicio', 'Permanencia', 'Permanencia semestral']


def test_breadcrumb_current_override_links_the_item_and_appends_the_page(app):
    with app.test_request_context():
        user = _user('program_admin', COORDINATOR)
        nav = Navigation.for_user(user, 'pages_student_record.student_record')
        crumbs = nav.breadcrumbs('Ana Pérez')
    assert [c['label'] for c in crumbs] == ['Inicio', 'Expedientes', 'Estudiantes', 'Ana Pérez']
    assert crumbs[2]['href'] and crumbs[3]['href'] is None


def test_empty_navigation_is_harmless():
    nav = Navigation.empty()
    assert nav.groups == () and nav.active_group is None
    assert nav.title is None and nav.breadcrumbs() == []


# ── Rendering ────────────────────────────────────────────────────────────────

def _login(client, user):
    from tests.support.fixtures import login_as
    return login_as(client, user)


def test_dashboard_renders_menu_with_active_group_open_server_side(app, client):
    user = _user('program_admin', COORDINATOR)
    _login(client, user)
    html = client.get('/coordinator/deliberation').get_data(as_text=True)

    # The Admisión group is current: open, expanded and marked for base.js.
    assert re.search(r'data-dropdown="nav-admision"\s+data-nav-current="true"\s+'
                     r'aria-expanded="true"', html)
    assert 'class="dropdown-submenu show" id="nav-admision"' in html
    assert re.search(r'class="nav-link submenu-item active"\s+href="/coordinator/deliberation"'
                     r'\s+aria-current="page"', html)
    # Other groups stay collapsed.
    assert re.search(r'data-dropdown="nav-configuracion"\s+'
                     r'aria-expanded="false"', html)
    # Breadcrumb in the page header.
    assert 'aria-label="Ruta de navegación"' in html
    assert re.search(r'<li class="breadcrumb-item active" aria-current="page">Deliberación</li>', html)
    # Default title derived from the menu; no English "Dashboard".
    assert '<title>Deliberación' in html
    assert 'Dashboard' not in html.split('<body')[1].split('<main')[0]


def test_header_has_one_logo_and_footer_has_the_four_institutional_ones(app, client):
    _login(client, _user('program_admin', COORDINATOR))
    html = client.get('/user/dashboard').get_data(as_text=True)
    header = html.split('<header', 1)[1].split('</header>', 1)[0]
    footer = html.split('<footer', 1)[1].split('</footer>', 1)[0]
    assert header.count('<img') == 1
    for alt in ('SEP', 'TecNM', 'ITCJ', 'Posgrado'):
        assert f'alt="{alt}"' in footer

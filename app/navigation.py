"""
Main navigation of the authenticated shell, defined as data.

The menu is organised by workflow (Inicio, Admisión, Permanencia, Eventos,
Expedientes, Configuración). `MENU` is the only place that says which links
exist, what permission each one needs and which endpoints keep it highlighted.
`_sidebar_nav.html` renders whatever `Navigation` resolves for the viewer; no
template carries an `if has_perm(...)` block for the menu any more.

Permissions here answer "may this person open the page", never "over which
program": scope stays in the routes (`program_scope_required`).

Every `NavItem.any_of` / `all_of` codename is the one the target route's
`@permission_required` decorator asks for, so a link is visible exactly when
the click would not end in a 403.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from flask import url_for

# Label of the first breadcrumb. It points at the user's landing page.
HOME_LABEL = 'Inicio'
HOME_ENDPOINT = 'pages_user.dashboard'

# Score of an exact endpoint match; a prefix match scores its own length, which
# is always smaller, so exact wins and a longer prefix beats a shorter one.
_EXACT_SCORE = 10_000


@dataclass(frozen=True)
class NavItem:
    """One link of the menu (declarative; resolved per viewer by Navigation)."""

    key: str
    label: str
    icon: str                              # Bootstrap Icons class, e.g. 'bi-house-door'
    endpoint: str
    any_of: tuple[str, ...] = ()           # visible if the viewer holds ANY of these
    all_of: tuple[str, ...] = ()           # ...and ALL of these ((): no extra condition)
    active_endpoints: tuple[str, ...] = ()  # extra exact endpoints that highlight it
    active_prefixes: tuple[str, ...] = ()   # endpoint prefixes that highlight it
    url_params: Optional[str] = None       # key into URL_PARAMS (None: no url arguments)
    badge: Optional[str] = None            # 'invitations' -> live counter span


@dataclass(frozen=True)
class NavGroup:
    """A workflow stage: a set of related links."""

    key: str
    label: str
    icon: str
    items: tuple[NavItem, ...]
    collapsible: bool = True               # False: always-visible flat section


# ── URL argument resolvers ───────────────────────────────────────────────────
# Return the url_for kwargs for the viewer, or None to hide the item.

def _enrolled_program_args(user) -> Optional[dict]:
    link = next(iter(user.user_program), None)
    if link is None or link.program is None:
        return None
    return {'slug': link.program.slug}


def _coordinated_program_args(user) -> Optional[dict]:
    """Program the viewer coordinates; global admins reach programs by the list."""
    if user.has_permission('academic_periods.api.create'):
        return None
    programs = user.coordinated_programs
    if not programs:
        return None
    return {'slug': programs[0].slug}


URL_PARAMS: dict[str, Callable] = {
    'enrolled_program': _enrolled_program_args,
    'coordinated_program': _coordinated_program_args,
}


# ── The menu ─────────────────────────────────────────────────────────────────

MENU: tuple[NavGroup, ...] = (
    NavGroup(
        key='inicio', label='Inicio', icon='bi-house-door', collapsible=False,
        items=(
            NavItem('home', 'Inicio', 'bi-house-door', 'pages_user.dashboard'),
            NavItem('profile', 'Perfil', 'bi-person', 'pages_user.profile'),
            NavItem('my-kardex', 'Mi kardex', 'bi-journal-check', 'pages_kardex.my_kardex',
                    any_of=('kardex.page.view_own',)),
        ),
    ),
    NavGroup(
        key='admision', label='Admisión', icon='bi-clipboard-check',
        items=(
            NavItem('programs', 'Programas', 'bi-mortarboard', 'program.list_programs',
                    active_endpoints=('program.view_program',)),
            NavItem('my-admission', 'Mi admisión', 'bi-clipboard-data',
                    'program.admission.admission_dashboard',
                    # The page asks for submissions.api.upload, but students hold
                    # it too; programs.api.enroll is what marks an applicant.
                    all_of=('submissions.api.upload', 'programs.api.enroll'),
                    url_params='enrolled_program'),
            NavItem('review', 'Revisión de documentos', 'bi-file-earmark-text',
                    'pages_admin.pages_review.index',
                    any_of=('admin_review.page.view',),
                    active_endpoints=('pages_admin.home',),
                    active_prefixes=('pages_admin.pages_review.',)),
            NavItem('deliberation', 'Deliberación', 'bi-hammer',
                    'pages_coordinator.deliberation',
                    any_of=('deliberation.page.view',)),
            NavItem('acceptance', 'Aceptación', 'bi-file-earmark-check',
                    'pages_coordinator.acceptance',
                    any_of=('acceptance.page.view',)),
        ),
    ),
    NavGroup(
        key='permanencia', label='Permanencia', icon='bi-calendar2-check',
        items=(
            NavItem('permanence', 'Permanencia semestral', 'bi-calendar2-check',
                    'pages_coordinator.permanence',
                    any_of=('permanence.page.view',)),
        ),
    ),
    NavGroup(
        key='eventos', label='Eventos', icon='bi-calendar-event',
        items=(
            NavItem('events', 'Eventos públicos', 'bi-calendar',
                    'pages_events_public.list_events',
                    active_prefixes=('pages_events_public.',),
                    badge='invitations'),
            NavItem('events-admin', 'Gestión de eventos', 'bi-calendar-plus',
                    'pages_admin.pages_events.index',
                    any_of=('events.page.view',),
                    active_prefixes=('pages_admin.pages_events.',)),
        ),
    ),
    NavGroup(
        key='expedientes', label='Expedientes', icon='bi-folder2-open',
        items=(
            NavItem('students', 'Estudiantes', 'bi-people',
                    'pages_coordinator.dashboard',
                    any_of=('coordinator.page.view',),
                    active_prefixes=('pages_student_record.',)),
            NavItem('bulk-import', 'Alta masiva', 'bi-people-fill',
                    'pages_admin.pages_settings.student_bulk_import',
                    any_of=('student_bulk.page.view',)),
        ),
    ),
    NavGroup(
        key='docencia', label='Docencia', icon='bi-easel',
        items=(
            NavItem('my-groups', 'Mis grupos', 'bi-people',
                    'pages_teaching.my_groups',
                    any_of=('teaching.page.my_groups',),
                    active_prefixes=('pages_teaching.',)),
        ),
    ),
    NavGroup(
        key='configuracion', label='Configuración', icon='bi-gear',
        items=(
            NavItem('files', 'Archivos', 'bi-folder',
                    'pages_admin.pages_settings.index',
                    any_of=('archives.api.list',),
                    active_endpoints=('pages_admin.pages_settings.retention',)),
            NavItem('users', 'Usuarios', 'bi-person-gear',
                    'pages_admin.pages_settings.users',
                    any_of=('admin_users.page.view',)),
            NavItem('emails', 'Correos', 'bi-envelope',
                    'pages_admin.pages_emails.email_config',
                    any_of=('admin_emails.api.manage',),
                    active_prefixes=('pages_admin.pages_emails.',)),
            NavItem('templates', 'Plantillas', 'bi-file-earmark-text',
                    'pages_admin.pages_settings.document_templates',
                    any_of=('admin_templates.page.view',)),
            NavItem('program-config', 'Mi programa', 'bi-mortarboard',
                    'pages_admin.pages_settings.config_program',
                    any_of=('coordinator.page.view',),
                    url_params='coordinated_program'),
            NavItem('programs-config', 'Configurar programas', 'bi-mortarboard-fill',
                    'program.list_programs',
                    any_of=('academic_periods.api.create',),
                    active_endpoints=('pages_admin.pages_settings.config_program',)),
            NavItem('curriculum', 'Planes de estudio', 'bi-journal-bookmark',
                    'pages_curriculum.index',
                    any_of=('curriculum.page.manage',),
                    active_prefixes=('pages_curriculum.',)),
            NavItem('grade-corrections', 'Correcciones de calificaciones', 'bi-pencil-square',
                    'pages_grade_corrections.index',
                    any_of=('grades.page.decide_correction',),
                    active_prefixes=('pages_grade_corrections.',)),
            NavItem('periods', 'Periodos académicos', 'bi-calendar3',
                    'pages_admin.pages_settings.academic_periods',
                    any_of=('academic_periods.api.create',)),
            NavItem('celery', 'Tareas programadas', 'bi-robot',
                    'pages_admin.pages_settings.celery_worker',
                    any_of=('admin_celery.api.manage',)),
            NavItem('permissions', 'Permisos', 'bi-shield-lock',
                    'pages_admin.pages_settings.permissions_manager',
                    any_of=('permissions.page.manage_roles',)),
            NavItem('cleanup', 'Limpieza de datos', 'bi-archive',
                    'pages_admin.pages_settings.data_cleanup',
                    any_of=('admin.page.purge',)),
        ),
    ),
)


# ── Resolution per viewer ────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResolvedItem:
    key: str
    label: str
    icon: str
    href: str
    badge: Optional[str]
    active: bool


@dataclass(frozen=True)
class ResolvedGroup:
    key: str
    label: str
    icon: str
    collapsible: bool
    items: tuple[ResolvedItem, ...]
    current: bool                          # holds the active item

    @property
    def is_single(self) -> bool:
        """A collapsible group with one visible link renders as that link."""
        return self.collapsible and len(self.items) == 1


def _is_visible(user, item: NavItem) -> bool:
    if item.any_of and not any(user.has_permission(c) for c in item.any_of):
        return False
    return all(user.has_permission(c) for c in item.all_of)


def _match_score(item: NavItem, endpoint: Optional[str]) -> int:
    """0 = no match; exact beats prefix; a longer prefix beats a shorter one."""
    if not endpoint:
        return 0
    if endpoint == item.endpoint or endpoint in item.active_endpoints:
        return _EXACT_SCORE
    best = 0
    for prefix in item.active_prefixes:
        if endpoint.startswith(prefix):
            best = max(best, len(prefix))
    return best


class Navigation:
    """The menu as seen by one viewer on one page."""

    def __init__(self, groups: tuple[ResolvedGroup, ...] = ()):
        self.groups = groups

    @classmethod
    def empty(cls) -> 'Navigation':
        return cls(())

    @classmethod
    def for_user(cls, user, endpoint: Optional[str]) -> 'Navigation':
        """Resolve visibility, hrefs and the active item for `user` on `endpoint`."""
        visible: list[tuple[NavGroup, list[tuple[NavItem, str]]]] = []
        for group in MENU:
            entries = []
            for item in group.items:
                if not _is_visible(user, item):
                    continue
                kwargs = {}
                if item.url_params:
                    kwargs = URL_PARAMS[item.url_params](user)
                    if kwargs is None:
                        continue
                entries.append((item, url_for(item.endpoint, **kwargs)))
            if entries:
                visible.append((group, entries))

        # Best match wins; on a tie the earlier item in MENU order does.
        active_key, best = None, 0
        for group, entries in visible:
            for item, _href in entries:
                score = _match_score(item, endpoint)
                if score > best:
                    active_key, best = (group.key, item.key), score

        groups = tuple(
            ResolvedGroup(
                key=group.key, label=group.label, icon=group.icon,
                collapsible=group.collapsible,
                items=tuple(
                    ResolvedItem(item.key, item.label, item.icon, href, item.badge,
                                 active=(group.key, item.key) == active_key)
                    for item, href in entries
                ),
                current=bool(active_key and active_key[0] == group.key),
            )
            for group, entries in visible
        )
        return cls(groups)

    # -- active state --------------------------------------------------------

    @property
    def active_group(self) -> Optional[ResolvedGroup]:
        return next((g for g in self.groups if g.current), None)

    @property
    def active_item(self) -> Optional[ResolvedItem]:
        group = self.active_group
        return next((i for i in group.items if i.active), None) if group else None

    @property
    def title(self) -> Optional[str]:
        """Default page title: the label of the active link."""
        item = self.active_item
        return item.label if item else None

    def breadcrumbs(self, current: Optional[str] = None) -> list[dict]:
        """
        Trail for the page header: [{'label', 'href'|None}], last one is the page.

        Home > Group > Item by default. `current` (a page-specific label such as
        a record name) turns the active item into a link and becomes the last
        crumb. Empty when the page is not part of the menu.
        """
        group, item = self.active_group, self.active_item
        if group is None or item is None:
            return []

        crumbs: list[dict] = []
        if group.key != 'inicio':
            crumbs.append({'label': HOME_LABEL, 'href': url_for(HOME_ENDPOINT)})
            if group.label != item.label:
                crumbs.append({'label': group.label, 'href': None})
        elif item.key != 'home':
            crumbs.append({'label': HOME_LABEL, 'href': url_for(HOME_ENDPOINT)})

        if current:
            crumbs.append({'label': item.label, 'href': item.href})
            crumbs.append({'label': current, 'href': None})
        else:
            crumbs.append({'label': item.label, 'href': None})
        return crumbs

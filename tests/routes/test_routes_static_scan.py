"""Step 1 — static AST scan of app/routes/** for permission codenames and decorators."""

import ast

from tests.routes import _helpers as h

# Codenames that currently break the `{resource}.{api|page}.{action}` convention.
# Empty on purpose: a NEW offender must fail this test, not be added silently.
ALLOWED_BAD_CODENAMES = frozenset()

# Decorators that register a view.
ROUTE_DECORATORS = {'route', 'get', 'post', 'put', 'patch', 'delete'}

# View functions that intentionally have NO @login_required (public surface).
PUBLIC_VIEW_FUNCS = {
    ('app/routes/api/auth_api.py', 'api_login'),
    ('app/routes/api/auth_api.py', 'api_reset_password'),
    ('app/routes/api/auth_api.py', 'api_reset_password_info'),
    ('app/routes/api/health_api.py', 'health_check'),
    ('app/routes/api/health_api.py', 'readiness_check'),
    ('app/routes/pages/auth.py', 'login_page'),
    ('app/routes/pages/auth.py', 'register_page'),
    ('app/routes/pages/auth.py', 'reset_password_page'),
}


def _views():
    views, _ = h.scan_routes()
    return views


def _route_views():
    return [v for v in _views() if set(v['decorators']) & ROUTE_DECORATORS]


def test_scan_finds_codenames():
    codenames = h.all_codenames()
    assert len(codenames) > 100, 'the AST scan lost most codenames; scanner broken?'


def test_every_codename_matches_convention():
    _, found = h.scan_routes()
    offenders = {(f, l, c) for f, l, c, _ in found if not h.CODENAME_RE.match(c)}
    unexpected = {o for o in offenders if o[2] not in ALLOWED_BAD_CODENAMES}
    assert not unexpected, f'codenames violating resource.(api|page).action: {sorted(unexpected)}'


def test_api_routes_use_api_codenames_and_pages_use_page_codenames():
    """A decorator on an /api blueprint file should not demand a `.page.` codename (and vice versa)."""
    mismatches = []
    for v in _views():
        for c in v['perms']:
            kind = c.split('.')[1] if c.count('.') >= 2 else None
            in_api = '/routes/api/' in v['file']
            if kind and ((in_api and kind != 'api') or (not in_api and kind != 'page')):
                mismatches.append((v['file'], v['func'], c))
    # Informational allow-list: pin whatever exists today so new drift fails.
    assert sorted(mismatches) == sorted(KNOWN_KIND_MISMATCHES), sorted(mismatches)


# Page views that deliberately reuse an `.api.` codename (no `.page.` twin exists).
KNOWN_KIND_MISMATCHES = [
    ('app/routes/pages/admin/email_pages.py', 'email_config', 'admin_emails.api.manage'),
    ('app/routes/pages/admin/email_pages.py', 'email_connection', 'admin_emails.api.manage'),
    ('app/routes/pages/admin/email_pages.py', 'get_email_queue', 'admin_emails.api.manage'),
    ('app/routes/pages/admin/email_pages.py', 'ms_callback', 'admin_emails.api.manage'),
    ('app/routes/pages/admin/email_pages.py', 'ms_login', 'admin_emails.api.manage'),
    ('app/routes/pages/admin/email_pages.py', 'ms_logout', 'admin_emails.api.manage'),
    ('app/routes/pages/admin/email_pages.py', 'process_email_queue', 'admin_emails.api.manage'),
    ('app/routes/pages/admin/email_pages.py', 'retry_failed_emails', 'admin_emails.api.manage'),
    ('app/routes/pages/admin/setting_pages.py', 'academic_periods', 'academic_periods.api.create'),
    ('app/routes/pages/admin/setting_pages.py', 'celery_worker', 'admin_celery.api.manage'),
    ('app/routes/pages/admin/setting_pages.py', 'index', 'archives.api.list'),
    ('app/routes/pages/admin/setting_pages.py', 'retention', 'admin_retention.api.manage'),
    ('app/routes/pages/admission_pages.py', 'admission_dashboard', 'submissions.api.upload'),
    ('app/routes/pages/admission_pages.py', 'admission_panel', 'submissions.api.upload'),
    ('app/routes/pages/admission_pages.py', 'delete_submission', 'submissions.api.delete_own'),
    ('app/routes/pages/admission_pages.py', 'upload_document', 'submissions.api.create'),
    # Phase 6C, decision 5: the enrolled student uploads an admission document
    # under an extension through the same admission upload (same permission).
    ('app/routes/pages/users_pages.py', 'upload_extension_document', 'submissions.api.create'),
    ('app/routes/pages/programs_pages.py', 'inscription_program', 'programs.api.enroll'),
    ('app/routes/pages/student_record_pages.py', 'record_admission_upload', 'coordinator.api.upload_for_student'),
    ('app/routes/pages/student_record_pages.py', 'record_trajectory_graduate', 'permanence.api.register_graduation'),
    ('app/routes/pages/student_record_pages.py', 'record_trajectory_revert_withdrawal', 'permanence.api.revert_withdrawal'),
    ('app/routes/pages/student_record_pages.py', 'record_trajectory_withdraw', 'permanence.api.withdraw'),
]


def test_permission_views_also_require_login():
    missing, misordered = [], []
    for v in _views():
        if not v['perms']:
            continue
        decs = v['decorators']
        if 'login_required' not in decs:
            missing.append((v['file'], v['func'], v['line']))
            continue
        first_perm = min(i for i, d in enumerate(decs) if d in h.PERM_DECORATORS)
        if decs.index('login_required') > first_perm:
            misordered.append((v['file'], v['func'], v['line']))
    assert not missing, f'permission-guarded views without @login_required: {missing}'
    assert not misordered, f'@login_required must sit ABOVE the permission decorator: {misordered}'


def test_route_views_without_login_are_the_documented_public_ones():
    open_views = {
        (v['file'], v['func']) for v in _route_views()
        if 'login_required' not in v['decorators']
    }
    unexpected = open_views - PUBLIC_VIEW_FUNCS
    assert not unexpected, f'route views reachable without @login_required: {sorted(unexpected)}'
    stale = PUBLIC_VIEW_FUNCS - open_views
    assert not stale, f'public allow-list entries that no longer exist / now require login: {sorted(stale)}'


def test_no_deprecated_decorators_or_kwargs():
    bad = []
    for path in sorted(h.ROUTES_DIR.rglob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = h._decorator_name(node)
                if name == 'roles_required':
                    bad.append((path.name, node.lineno, 'roles_required'))
                if name in h.PERM_DECORATORS and any(k.arg == 'program_id_kwarg' for k in node.keywords):
                    bad.append((path.name, node.lineno, 'program_id_kwarg'))
    assert not bad, bad

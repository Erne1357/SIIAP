"""Shared helpers for the route-coverage tests (not collected by pytest)."""

import ast
import re
import uuid
from pathlib import Path

ROUTES_DIR = Path(__file__).resolve().parents[2] / 'app' / 'routes'
CODENAME_RE = re.compile(r'^[a-z_]+\.(api|page)\.[a-z_]+$')
PERM_DECORATORS = {'permission_required', 'any_permission_required'}

DUMMY_UUID = '01900000-0000-7000-8000-000000000001'
DUMMY_INT = 999999


def _decorator_name(dec):
    node = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _str_args(call):
    return [a.value for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]


def scan_routes():
    """AST scan over app/routes/**.

    Returns (views, codenames) where views is a list of dicts with keys
    file, func, line, decorators (names), perms (codenames from decorators),
    and codenames is a list of (file, line, codename, kind) for every
    permission_required / any_permission_required / has_permission usage.
    """
    views, codenames = [], []
    for path in sorted(ROUTES_DIR.rglob('*.py')):
        rel = path.relative_to(ROUTES_DIR.parents[1]).as_posix()
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names, perms = [], []
                for dec in node.decorator_list:
                    n = _decorator_name(dec)
                    names.append(n)
                    if n in PERM_DECORATORS and isinstance(dec, ast.Call):
                        perms.extend(_str_args(dec))
                views.append({'file': rel, 'func': node.name, 'line': node.lineno,
                              'decorators': names, 'perms': perms})
            elif isinstance(node, ast.Call):
                n = _decorator_name(node)
                if n in PERM_DECORATORS or n == 'has_permission':
                    for c in _str_args(node):
                        codenames.append((rel, node.lineno, c, n))
    return views, codenames


def all_codenames():
    _, found = scan_routes()
    return sorted({c for _, _, c, _ in found})


def fill_rule(rule):
    """Return a concrete URL for a werkzeug Rule using dummy converter values."""
    values = {}
    for arg in rule.arguments:
        conv = rule._converters.get(arg)
        cname = type(conv).__name__ if conv is not None else 'UnicodeConverter'
        if cname == 'IntegerConverter':
            values[arg] = DUMMY_INT
        elif cname == 'UUIDConverter':
            values[arg] = uuid.UUID(DUMMY_UUID)
        else:
            values[arg] = 'x'
    _, url = rule.build(values, append_unknown=False)
    return url


def iter_cases(app, *, api=None, methods=None):
    """Yield (id, method, url, rule) for every (rule, method) in the url_map."""
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: (r.rule, r.endpoint)):
        is_api = rule.rule.startswith('/api/')
        if api is not None and is_api != api:
            continue
        for m in sorted(rule.methods - {'HEAD', 'OPTIONS'}):
            if methods and m not in methods:
                continue
            yield f'{m} {rule.rule}', m, fill_rule(rule), rule


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

# (METHOD, rule) pairs reachable WITHOUT a session. Everything else in the
# url_map must reject an anonymous caller.
PUBLIC = frozenset({
    'GET /login',
    'GET /register',
    'POST /register',
    'GET /reset-password/<token>',
    'GET /health',
    'GET /ready',
    'GET /static/<path:filename>',
    'POST /api/v1/auth/login',
    'POST /api/v1/auth/reset-password/<token>',
    'GET /api/v1/auth/reset-password/<token>/info',
})

# Public routes that sit in front of the login manager and the CSRF guard.
CSRF_EXEMPT = frozenset({'POST /api/v1/auth/login'})


# Routes that need only a session (login_required, no permission decorator):
# a user with zero grants legitimately reaches them.
LOGIN_ONLY = frozenset({
    'GET /', 'GET /events/', 'GET /programs/', 'GET /user/dashboard', 'GET /user/profile',
    'GET /user/dashboard/events-widget', 'GET /user/profile/summary',
    'GET /api/v1/appointments/mine/active', 'GET /api/v1/archives', 'GET /api/v1/archives/steps',
    'POST /api/v1/attendance/event/<int:event_id>/unregister', 'GET /api/v1/attendance/my-registrations',
    'POST /api/v1/auth/change-password', 'GET /api/v1/auth/keepalive', 'GET /api/v1/auth/session-status', 'GET /api/v1/auth/logout',
    'POST /api/v1/auth/logout', 'GET /api/v1/auth/me',
    'POST /api/v1/events/mark-seen', 'GET /api/v1/events/new-count', 'GET /api/v1/events/public',
    'POST /api/v1/extensions/requests', 'GET /api/v1/extensions/requests',
    'POST /api/v1/invitations/<int:invitation_id>/respond', 'GET /api/v1/invitations/my-invitations',
    'GET /api/v1/notifications', 'POST /api/v1/notifications/<int:notification_id>/respond-invitation',
    'POST /api/v1/notifications/clear-read', 'POST /api/v1/notifications/mark-all-read',
    'GET /api/v1/notifications/unread-count',
    'POST /api/v1/permanence/user-program/<int:user_program_id>/documents/<int:deadline_id>',
    'POST /api/v1/permanence/user-program/<int:user_program_id>/leave-request',
    'GET /api/v1/permissions/me',
    # owner-scoped: answer 404 for an id that is not the caller's own
    'GET /api/v1/events/public/<int:event_id>', 'DELETE /api/v1/notifications/<int:notification_id>',
    'PATCH /api/v1/notifications/<int:notification_id>/read',
    'GET /api/v1/extensions/archive/<uuid:archive_uuid>/status',
    'POST /api/v1/program-changes', 'POST /api/v1/program-changes/analyze',
    'POST /api/v1/program-changes/execute', 'GET /api/v1/program-changes/requests',
    'GET /api/v1/programs', 'GET /api/v1/users/me', 'PATCH /api/v1/users/me',
    'PATCH /api/v1/users/me/complete-profile', 'GET /api/v1/users/me/history',
    'GET /api/v1/users/me/photo-status', 'GET /api/v1/users/me/profile-completion',
})

# Real defects found by these matrices. Value = reason; the matching case is
# marked xfail(strict=True) so fixing the bug flips the suite red until the
# entry is removed.
KNOWN_BUGS = {
    # (matrix, case id) -> reason. Empty: the three bugs this matrix found
    # (/admin/ 500, 400 redirect to None, schedules on a non-redis broker) are
    # fixed and now pinned as ordinary cases.
}

_CASES = []


def get_cases():
    """Build one throwaway app and cache (id, method, url, rule.rule, is_api) tuples."""
    if not _CASES:
        import pathlib
        import tempfile
        from app import create_app
        from tests.support.fixtures import make_test_config
        app = create_app(make_test_config(pathlib.Path(tempfile.mkdtemp())))
        for id_, m, url, rule in iter_cases(app):
            _CASES.append((id_, m, url, rule.rule, rule.rule.startswith('/api/'), tuple(sorted(rule.arguments))))
    return list(_CASES)


def case_params(matrix=None, *, only=None):
    """pytest params for get_cases(), applying KNOWN_BUGS xfails for `matrix`."""
    import pytest
    out = []
    for id_, m, url, rule, is_api, args in get_cases():
        if only and not only(id_, m, url, rule, is_api, args):
            continue
        reason = KNOWN_BUGS.get((matrix, id_))
        marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
        out.append(pytest.param(id_, m, url, rule, is_api, id=id_, marks=marks))
    return out

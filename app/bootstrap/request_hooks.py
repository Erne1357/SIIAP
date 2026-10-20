"""before_request hooks: session timeout, malformed API paths, password guard.

The registration order below is the execution order of the hooks.
"""
from flask import flash, jsonify, redirect, request, session, url_for
from flask_login import current_user, logout_user

from app.utils.datetime_utils import now_local
from app.utils.htmx import hx_redirect, wants_html_fragment


def register_request_hooks(app):
    @app.before_request
    def _enforce_session_timeout():
        """Gestiona la expiración de sesión por inactividad."""
        safe_endpoints = {
            'pages_auth.login_page',
            'pages_auth.register_page',
            'api_auth.api_login',
            'api_auth.api_logout',
            'api_auth.api_keepalive',
            'api_health.health_check',
            'api_health.readiness_check',
            'static',
        }

        if request.endpoint in safe_endpoints:
            return

        session.permanent = True
        now_ts = now_local().timestamp()
        last_activity = session.get('last_activity')

        if current_user.is_authenticated:
            if last_activity:
                if now_ts - last_activity > 15 * 60:
                    session.clear()
                    logout_user()
                    if wants_html_fragment():
                        # A 302 would be followed by htmx and the login page
                        # injected into the swap target; navigate instead.
                        flash("Tu sesión ha expirado por inactividad.", "warning")
                        return hx_redirect(url_for('pages_auth.login_page'), status=401)
                    if request.endpoint != 'pages_auth.login_page' and \
                            not request.path.startswith('/api/'):
                        flash("Tu sesión ha expirado por inactividad.", "warning")
                    if request.path.startswith('/api/'):
                        return jsonify({
                            "data": None,
                            "error": {"code": "SESSION_EXPIRED", "message": "Sesión expirada"},
                            "meta": {}
                        }), 401
                    return redirect(url_for('pages_auth.login_page'))

            session['last_activity'] = now_ts

            # Registra presencia activa del usuario en Redis (para contador de online)
            try:
                from app.utils.session_tracker import track_user_session
                track_user_session(current_user.id)
            except Exception:
                pass  # Redis caído no debe interrumpir la request

    @app.before_request
    def reject_malformed_api_paths():
        """
        Rechaza rutas /api/v1/* donde un segmento del path o un valor de query
        contiene literales 'undefined' / 'null' / 'NaN' producidos por bugs en JS
        (template literal interpolando una variable indefinida).

        En lugar de devolver 404 críptico o reventar al castear a int, devolvemos
        400 con código MALFORMED_PATH para que el bug sea evidente en el frontend.
        """
        if not request.path.startswith('/api/'):
            return None

        BAD_TOKENS = ('undefined', 'null', 'NaN')

        # Path segments
        for segment in request.path.split('/'):
            if segment in BAD_TOKENS:
                return jsonify({
                    "data": None,
                    "error": {
                        "code": "MALFORMED_PATH",
                        "message": f"Segmento inválido '{segment}' en la URL — probable bug de frontend (variable sin definir).",
                        "path": request.path,
                    },
                    "meta": {}
                }), 400

        # Query string values
        # multi=True: `?id=1&id=undefined` must not slip through on the first value.
        for key, value in request.args.items(multi=True):
            if value in BAD_TOKENS:
                return jsonify({
                    "data": None,
                    "error": {
                        "code": "MALFORMED_QUERY",
                        "message": f"Parámetro '{key}={value}' inválido — probable bug de frontend (variable sin definir).",
                        "path": request.full_path,
                    },
                    "meta": {}
                }), 400

        return None

    @app.before_request
    def check_password_change_required():
        """
        Fuerza el cambio de contraseña si must_change_password=True.

        An API/XHR call gets the 403 envelope; a browser navigation is pinned to
        the page that hosts the forced-change modal. Falling through to None on
        a plain GET (the previous behaviour) made the flag purely advisory: the
        user typed the dashboard URL and was in, modal or no modal.
        """
        if not current_user.is_authenticated:
            return None
        if not getattr(current_user, 'must_change_password', False):
            return None

        # Matched by endpoint name, not by path prefix, so a future route that
        # merely shares a prefix is not exempted by accident.
        #   static                         → CSS/JS, incl. force_password_change.js
        #   pages_user.dashboard           → the redirect target below; it renders
        #                                    base.html, which carries the modal
        #   pages_auth.login_page          → the view itself bounces an already
        #                                    authenticated user to the dashboard
        #   pages_auth.reset_password_page → token-based flow that logs the user
        #                                    out; another legitimate way to set a
        #                                    new password, so it must stay open
        allowed_endpoints = {
            'static',
            'pages_user.dashboard',
            'pages_auth.login_page',
            'pages_auth.reset_password_page',
        }
        if request.endpoint in allowed_endpoints:
            return None

        # Kept as prefixes: this is the API contract the modal itself speaks.
        # '/auth/logout' was dropped — no such route exists; logout is
        # api_auth.api_logout at /api/v1/auth/logout, already listed here.
        allowed_paths = (
            '/api/v1/auth/change-password',   # the fix itself
            '/api/v1/auth/logout',            # escape hatch
            '/api/v1/auth/me',                # modal reads must_change_password here
            '/api/v1/auth/keepalive',         # the session must survive the typing
            # The set-password-by-token flow is the other legitimate way to
            # leave this state. The PAGE endpoint being exempt is not enough:
            # its XHRs hit these two, and they only work today because
            # reset_password_page() happens to call logout_user() on load,
            # which makes the later calls anonymous. That is an undeclared
            # order dependency — a bfcache resubmit or any change to that page
            # would kill the flow silently. Exempt the API explicitly.
            '/api/v1/auth/reset-password/',
            '/static/',
            '/health',                        # docker health check
            '/ready',                         # blue-green readiness probe
        )
        # Segment-aware match: a bare startswith() admitted `/api/v1/auth/menu`
        # through `/api/v1/auth/me` and `/healthz` through `/health`.
        path = request.path
        for allowed in allowed_paths:
            if path == allowed.rstrip('/') or path.startswith(allowed.rstrip('/') + '/'):
                return None

        if wants_html_fragment():
            flash("Debes cambiar tu contraseña antes de continuar.", "warning")
            return hx_redirect(url_for('pages_user.dashboard'), status=403)

        if request.path.startswith('/api/') or request.is_json or \
                request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                "data": None,
                "flash": [{"level": "warning", "message": "Debes cambiar tu contraseña antes de continuar"}],
                "error": {
                    "code": "PASSWORD_CHANGE_REQUIRED",
                    "message": "Cambio de contraseña obligatorio",
                    "must_change_password": True
                },
                "meta": {}
            }), 403

        # Browser navigation. The target endpoint is in allowed_endpoints above,
        # so the redirected request returns None here instead of being redirected
        # again — one hop, never a loop.
        flash("Debes cambiar tu contraseña antes de continuar.", "warning")
        return redirect(url_for('pages_user.dashboard'))

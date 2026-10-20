"""HTTP and domain error handlers (JSON envelope for API/XHR, flash for pages)."""
from flask import flash, jsonify, redirect, render_template, request, url_for

from app.utils.csrf import CSRFError, csrf_error_message
from app.utils.htmx import hx_error, hx_redirect, wants_html_fragment


def register_error_handlers(app, login_manager):
    @app.errorhandler(404)
    def page_not_found(e):
        """
        404 — including the one Werkzeug raises BEFORE any view runs when a
        `<uuid:...>` path segment is malformed.

        API callers get the standard JSON envelope, like 400 and 403 already
        do; without this an XHR against a mistyped identifier received an HTML
        page and the frontend's `response.json()` blew up with a parse error
        instead of showing the message.

        The message is a FIXED generic string, never `e.description`: a
        malformed identifier, an unknown one and a row the caller may not see
        must be indistinguishable. Routes that need to say something more
        specific return their own 404 body from inside the view.
        """
        if wants_html_fragment():
            return hx_error(404, "Recurso no encontrado.")
        if request.path.startswith('/api/') or request.is_json or \
                request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            message = "Recurso no encontrado."
            return jsonify({
                "data": None,
                "flash": [{"level": "danger", "message": message}],
                "error": {"code": "NOT_FOUND", "message": message},
                "meta": {}
            }), 404
        return render_template('404.html', error=e), 404

    def _wants_json():
        return request.path.startswith('/api/') or request.is_json or \
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _error_envelope(status, code, message, level="danger"):
        return jsonify({
            "data": None,
            "flash": [{"level": level, "message": message}],
            "error": {"code": code, "message": message},
            "meta": {}
        }), status

    def _back_or_index():
        """Referrer to return to, never None and never the failing URL itself."""
        back = request.referrer
        if not back or back == request.url:
            back = url_for('index')
        return back

    @app.errorhandler(500)
    def internal_server_error(e):
        # API callers parse JSON; an HTML 500 page made `response.json()` throw
        # in the frontend and hid the failure behind a parse error.
        if wants_html_fragment():
            return hx_error(500, "Ocurrió un error interno. Intenta de nuevo más tarde.")
        if _wants_json():
            return _error_envelope(500, "SERVER_ERROR", "Ocurrió un error interno. Intenta de nuevo más tarde.")
        return render_template('500.html', error=e), 500

    @app.errorhandler(401)
    def unauthorized_error(e):
        # abort(401) from permission_required/any_permission_required had no
        # handler: API callers received Werkzeug's English HTML page.
        if wants_html_fragment():
            # htmx would follow a 302 and inject the login page into the target.
            flash(login_manager.login_message, login_manager.login_message_category)
            return hx_redirect(url_for(login_manager.login_view), status=401)
        if _wants_json():
            return _error_envelope(401, "UNAUTHORIZED", "No autenticado")
        flash(login_manager.login_message, login_manager.login_message_category)
        return redirect(url_for(login_manager.login_view))

    @app.errorhandler(405)
    def method_not_allowed(e):
        # RFC 9110: a 405 MUST list the allowed methods; Werkzeug's default
        # response did, so the custom one has to carry it over.
        allow = {'Allow': ', '.join(sorted(e.valid_methods or []))}
        if wants_html_fragment():
            resp = hx_error(405, "Método no permitido para este recurso.")
            resp.headers.update(allow)
            return resp
        if _wants_json():
            body, status = _error_envelope(405, "METHOD_NOT_ALLOWED", "Método no permitido para este recurso.")
            return body, status, allow
        return render_template('404.html', error=e), 405, allow

    @app.errorhandler(413)
    def payload_too_large(e):
        limit_mb = (app.config.get('MAX_CONTENT_LENGTH') or 0) // (1024 * 1024)
        message = f"El archivo excede el tamaño máximo permitido ({limit_mb} MB)."
        if wants_html_fragment():
            return hx_error(413, message)
        if _wants_json():
            return _error_envelope(413, "PAYLOAD_TOO_LARGE", message)
        flash(message, "danger")
        return redirect(_back_or_index(), code=303)

    @app.errorhandler(403)
    def forbidden(e):
        if wants_html_fragment():
            return hx_error(403, "No tienes permiso para acceder a este recurso.")
        if request.path.startswith('/api/') or request.is_json or \
                request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                "data": None,
                "flash": [{"level": "danger", "message": "No tienes permiso para acceder a este recurso."}],
                "error": {"code": "FORBIDDEN", "message": "No tienes permiso para acceder a este recurso."},
                "meta": {}
            }), 403
        flash("No tienes permiso para acceder a esta página.", "danger")
        code = 303 if request.method == 'POST' else 302
        return redirect(_back_or_index(), code=code)

    @app.errorhandler(400)
    def bad_request(e):
        # Our own abort(400, description=...) calls are Spanish; Werkzeug's
        # stock description is English and must never reach the UI.
        from werkzeug.exceptions import BadRequest
        message = e.description
        if not message or message == BadRequest.description:
            message = "La solicitud no es válida."
        if wants_html_fragment():
            return hx_error(400, message)
        if _wants_json():
            return _error_envelope(400, "BAD_REQUEST", message)
        flash(message, "danger")
        code = 303 if request.method == 'POST' else 302
        # Without a Referer this used to send `Location: None`.
        return redirect(_back_or_index(), code=code)

    @app.errorhandler(CSRFError)
    def csrf_failed(e):
        e.description = csrf_error_message(e)
        return bad_request(e)

    from app.services.errors import DomainError
    from app.utils.api_response import domain_error_response

    @app.errorhandler(DomainError)
    def domain_error(e):
        """
        Business-rule refusal raised by a service (Spanish message).

        Routes no longer need a try/except per domain exception: anything
        inheriting DomainError (InvalidAdmissionTransition, ValidationFailed,
        the per-service bases) lands here with its own status and code.
        """
        if wants_html_fragment():
            return hx_error(e.status_code, e.message or str(e), level=e.level)
        if _wants_json():
            return domain_error_response(e)
        flash(e.message or str(e), e.level)
        return redirect(_back_or_index(), code=303)

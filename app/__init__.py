from flask import Flask, jsonify, session, flash, redirect, url_for, render_template
from flask import request, has_request_context
from flask_sqlalchemy import SQLAlchemy
from flask_login import current_user, logout_user, LoginManager
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import timedelta
from app.utils.datetime_utils import now_local, format_date_es, format_datetime_es
from app.config import Config
from app.utils.csrf import CSRFError, csrf_error_message, generate_csrf_token, init_csrf
from app.extensions import socketio

db = SQLAlchemy()
login_manager = LoginManager()


def _socketio_allowed_origins(app):
    """
    Origins allowed to open the Socket.IO connection.

    The session cookie authenticates the socket, so '*' let any website open
    a live connection as the visitor (SameSite=Lax only stops it for some
    browsers). Production accepts its own public origin only.
    """
    if app.config.get('FLASK_ENV') != 'production':
        return '*'
    base = (app.config.get('APP_BASE_URL') or '').rstrip('/')
    return [base] if base else '*'


def create_app(test_config=None):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    # Aceptar rutas con o sin trailing slash sin emitir 308 redirect.
    # Evita que llamadas JS a /api/v1/x y /api/v1/x/ se comporten distinto.
    app.url_map.strict_slashes = False

    if test_config is None:
        app.config.from_object(Config)
    else:
        app.config.update(test_config)

    # Logging to stdout with a request id per line (collected into Loki by
    # the platform stack). Tests keep pytest's own handlers (caplog).
    from app.utils.logging_config import configure_logging, init_request_id
    if not app.testing:
        configure_logging()
    init_request_id(app)

    # ProxyFix para manejar headers de proxy reverso (HTTPS)
    if app.config.get('FLASK_ENV') == 'production':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # Every DateTime column is `timestamp without time zone` and the app writes
    # aware local datetimes (now_local()). PostgreSQL converts those using the
    # SESSION time zone, so a server left on UTC stores every timestamp 6-7 h
    # off and a just-expired token stays valid. Production only worked because
    # its cluster was initialised with TZ=America/Ciudad_Juarez; pin it here.
    if str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('postgres'):
        from app.utils.datetime_utils import LOCAL_TZ
        engine_options = app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {})
        connect_args = engine_options.setdefault('connect_args', {})
        connect_args.setdefault('options', f'-c timezone={LOCAL_TZ.key}')

    db.init_app(app)

    # Blueprints
    from app.routes.api import register_api_blueprints
    from app.routes.pages import register_page_blueprints
    register_api_blueprints(app)
    register_page_blueprints(app)
    
    # Inicializar Celery (evita ciclos de importación al no crear otra app)
    from app.celery_app import init_celery
    init_celery(app)

    # Socket.IO
    # Intentar usar Redis como message broker (requerido con múltiples workers).
    # Si Redis no está disponible, usamos message_queue=None (solo funciona con workers=1).
    # Under TESTING the queue is forced off below anyway, so the ping is skipped:
    # with the default host `redis` unresolvable it cost a DNS timeout per app.
    _redis_url = app.config.get('REDIS_URL', 'redis://redis:6379/0')
    _mq = None
    if not app.config.get('TESTING'):
        try:
            import redis as _redis_lib
            _r = _redis_lib.from_url(_redis_url, socket_connect_timeout=2, socket_timeout=2)
            _r.ping()
            _mq = _redis_url
        except Exception:
            app.logger.warning('[SocketIO] Redis no disponible — message_queue=None (single-worker mode)')

    if app.config.get('TESTING'):
        _async_mode = 'threading'
    else:
        try:
            import eventlet  # noqa: F401
            _async_mode = 'eventlet'
        except ImportError:
            _async_mode = 'threading'
    socketio.init_app(
        app,
        async_mode=_async_mode,
        message_queue=_mq,
        cors_allowed_origins=_socketio_allowed_origins(app),
        logger=False,
        engineio_logger=False,
    )
    from app.sockets import register_socket_handlers
    register_socket_handlers(socketio)

    # Login manager
    login_manager.init_app(app)
    login_manager.login_view = 'pages_auth.login_page'
    login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
    login_manager.login_message_category = "warning"

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith('/api/'):
            return jsonify({
                "data": None,
                "error": {"code": "UNAUTHORIZED", "message": "No autenticado"},
                "meta": {}
            }), 401
        if request.endpoint != 'pages_auth.login_page':
            flash(login_manager.login_message, login_manager.login_message_category)
        return redirect(url_for(login_manager.login_view))

    migrate = Migrate(app, db)

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        """
        Resolve the session cookie to a user.

        A malformed identifier resolves to "anonymous", never to an exception.
        int(user_id) on a cookie whose _user_id is not an integer (a stale
        cookie, or one minted on either side of the pending UUID migration)
        raised straight out of the login manager on EVERY request — including
        /login and /logout — so the victim could not clear the bad session from
        inside the app at all; the only way out was deleting the cookie by hand.

        Returns None for a deactivated account so that the very next request
        from an existing cookie is anonymous. Without this, deactivating a
        compromised account changed nothing for whoever already held a session:
        the before_request handler rewrote last_activity on every request, so
        the 15-minute idle window never closed and the cookie stayed valid
        indefinitely.
        """
        try:
            pk = int(user_id)
        except (TypeError, ValueError):
            return None
        user = User.query.get(pk)
        if user is None or not user.is_active:
            return None
        return user

    app.permanent_session_lifetime = timedelta(minutes=17)

    # ─── Error handlers ──────────────────────────────────────────────────────

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
        if _wants_json():
            return _error_envelope(500, "SERVER_ERROR", "Ocurrió un error interno. Intenta de nuevo más tarde.")
        return render_template('500.html', error=e), 500

    @app.errorhandler(401)
    def unauthorized_error(e):
        # abort(401) from permission_required/any_permission_required had no
        # handler: API callers received Werkzeug's English HTML page.
        if _wants_json():
            return _error_envelope(401, "UNAUTHORIZED", "No autenticado")
        flash(login_manager.login_message, login_manager.login_message_category)
        return redirect(url_for(login_manager.login_view))

    @app.errorhandler(405)
    def method_not_allowed(e):
        # RFC 9110: a 405 MUST list the allowed methods; Werkzeug's default
        # response did, so the custom one has to carry it over.
        allow = {'Allow': ', '.join(sorted(e.valid_methods or []))}
        if _wants_json():
            body, status = _error_envelope(405, "METHOD_NOT_ALLOWED", "Método no permitido para este recurso.")
            return body, status, allow
        return render_template('404.html', error=e), 405, allow

    @app.errorhandler(413)
    def payload_too_large(e):
        limit_mb = (app.config.get('MAX_CONTENT_LENGTH') or 0) // (1024 * 1024)
        message = f"El archivo excede el tamaño máximo permitido ({limit_mb} MB)."
        if _wants_json():
            return _error_envelope(413, "PAYLOAD_TOO_LARGE", message)
        flash(message, "danger")
        return redirect(_back_or_index(), code=303)

    @app.errorhandler(403)
    def forbidden(e):
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

    # Function-local import: the service imports `app.db`.
    from app.services.admission_status_service import InvalidAdmissionTransition

    @app.errorhandler(InvalidAdmissionTransition)
    def invalid_admission_transition(e):
        """Safety net for an unguarded status move refused by the state machine."""
        message = str(e)
        if _wants_json():
            return _error_envelope(400, "BUSINESS_ERROR", message, level="warning")
        flash(message, "warning")
        return redirect(_back_or_index(), code=303)

    # ─── Middleware / before_request ─────────────────────────────────────────

    # Registered before every other before_request hook: a forged mutation is
    # rejected before session bookkeeping or authentication run.
    init_csrf(app)

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

    def _viewer_is_authenticated():
        """
        True only when there is a real logged-in viewer.

        This context processor runs on EVERY render_template, including the
        email templates that Celery tasks render with no request context. There
        current_user resolves to None, so touching .is_authenticated raised
        AttributeError and killed the render.
        """
        if not has_request_context():
            return False
        return bool(current_user and current_user.is_authenticated)

    @app.context_processor
    def inject_tokens_and_version():
        def has_perm(codename):
            """
            Helper de Jinja2 para comprobar permisos en templates.

            Uso en plantillas:
                {% if has_perm('coordinator.page.view') %}

            Responde SÓLO "¿qué puede hacer?" — nunca "¿sobre qué programa?".
            Una plantilla no debe decidir alcance: eso lo resuelve la ruta con
            `program_scope_required` antes de renderizar.
            """
            # Fuera de una petición (p. ej. una plantilla de correo renderizada
            # desde una tarea de Celery) current_user resuelve a None y
            # .is_authenticated revienta con AttributeError.
            if not _viewer_is_authenticated():
                return False
            return current_user.has_permission(codename)

        def _role_info():
            """
            (label, badge_class) para el rol visible del usuario.
            Centraliza la lógica que antes vivía duplicada en base.html, profile.html, dashboard.html.
            """
            if not _viewer_is_authenticated():
                return (None, None)
            if current_user.has_global_program_scope():
                return ('Admin. Posgrado', 'bg-danger')
            if current_user.has_permission('coordinator.page.view'):
                return ('Admin. Programa', 'bg-success')
            if current_user.has_permission('admin_review.page.view'):
                return ('Servicio Social', 'bg-warning text-dark')
            if current_user.has_permission('permanence.api.view_status'):
                return ('Estudiante', 'bg-primary')
            if current_user.has_permission('programs.api.enroll'):
                return ('Aspirante', 'bg-info text-dark')
            return (None, None)

        role_label, role_badge_class = _role_info()

        return {
            "static_version": app.config.get("STATIC_VERSION", "1.0.0"),
            "csrf_token": generate_csrf_token,
            # Expuesto para que las plantillas no escriban el año a mano
            # (pie de página de base.html / auth_base.html).
            "now_local": now_local,
            "has_perm": has_perm,
            "role_label": role_label,
            "role_badge_class": role_badge_class,
        }

    _ES_STATUS = {
        'in_progress': 'En Proceso',
        'interview_completed': 'Entrevista Completada',
        'deliberation': 'En Deliberación',
        'accepted': 'Aceptado',
        'rejected': 'Rechazado',
        'deferred': 'Diferido',
        'enrolled': 'Inscrito',
        'pending': 'Pendiente',
        'active': 'Activo',
        'completed': 'Completado',
        'on_leave': 'Baja Temporal',
        'dropped': 'Baja Definitiva',
        'approved': 'Aprobado',
        'used': 'Usado',
        'expired': 'Expirado',
        'registered': 'Inscrito',
        'attended': 'Asistió',
        'absent': 'Ausente',
        'cancelled': 'Cancelado',
        'confirmed': 'Confirmado',
        'scheduled': 'Programado',
    }
    _ES_ROLE = {
        'applicant': 'Aspirante',
        'program_admin': 'Coord. de Programa',
        'postgraduate_admin': 'Admin. de Posgrado',
        'social_service': 'Servicio Social',
        'student': 'Estudiante',
    }
    _ES_ACCEPTANCE_DOC = {
        'acceptance_letter': 'Carta de Aceptación',
        'course_schedule': 'Tira de Materias',
        'enrollment_receipt': 'Boleta de Servicios Escolares',
        'acceptance_opinion': 'Dictamen de Aceptación',
    }

    @app.template_filter('es_status')
    def _es_status_filter(value):
        if not value:
            return '—'
        return _ES_STATUS.get(value, str(value).replace('_', ' '))

    @app.template_filter('es_role')
    def _es_role_filter(value):
        if not value:
            return '—'
        return _ES_ROLE.get(value, value)

    @app.template_filter('es_doc_type')
    def _es_doc_type_filter(value):
        if not value:
            return '—'
        return _ES_ACCEPTANCE_DOC.get(value, value)

    @app.template_filter('fecha_es')
    def _fecha_es_filter(value, style='long'):
        """Render a date in Spanish: 'long' | 'short' | 'numeric'."""
        return format_date_es(value, style)

    @app.template_filter('fechahora_es')
    def _fechahora_es_filter(value, style='long', include_time=True):
        """Render a datetime in Spanish wrapped in a semantic <time> element."""
        return format_datetime_es(value, style, include_time)

    @app.route('/')
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for('pages_auth.login_page'))
        return redirect(url_for('pages_user.dashboard'))

    # Registrar comandos CLI
    from app.cli import register_cli
    register_cli(app)

    return app


app = create_app()

from flask import Flask, jsonify, session, flash, redirect, url_for, render_template
from flask import request
from flask_sqlalchemy import SQLAlchemy
from flask_login import current_user, logout_user, LoginManager
from flask_migrate import Migrate
from flask_bootstrap import Bootstrap
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import timedelta
from app.utils.datetime_utils import now_local
from app.config import Config
from app.utils.csrf import generate_csrf_token, validate_csrf_for_api
from app.extensions import socketio

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(test_config=None):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    Bootstrap(app)

    if test_config is None:
        app.config.from_object(Config)
    else:
        app.config.update(test_config)

    # ProxyFix para manejar headers de proxy reverso (HTTPS)
    if app.config.get('FLASK_ENV') == 'production':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    db.init_app(app)

    # Blueprints
    from app.routes.api import register_api_blueprints
    from app.routes.pages import register_page_blueprints
    register_api_blueprints(app)
    register_page_blueprints(app)

    # Socket.IO
    # Intentar usar Redis como message broker (requerido con múltiples workers).
    # Si Redis no está disponible, usamos message_queue=None (solo funciona con workers=1).
    _redis_url = app.config.get('REDIS_URL', 'redis://redis:6379/0')
    try:
        import redis as _redis_lib
        _r = _redis_lib.from_url(_redis_url, socket_connect_timeout=2, socket_timeout=2)
        _r.ping()
        _mq = _redis_url
    except Exception:
        app.logger.warning('[SocketIO] Redis no disponible — message_queue=None (single-worker mode)')
        _mq = None

    socketio.init_app(
        app,
        async_mode='eventlet',
        message_queue=_mq,
        cors_allowed_origins='*',
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
        return User.query.get(int(user_id))

    app.permanent_session_lifetime = timedelta(minutes=17)

    # ─── Error handlers ──────────────────────────────────────────────────────

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html', error=e), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html', error=e), 500

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
        back = request.referrer
        if not back or back == request.url:
            back = url_for('index')
        code = 303 if request.method == 'POST' else 302
        return redirect(back, code=code)

    @app.errorhandler(400)
    def bad_request(e):
        if request.path.startswith('/api/') or request.is_json or \
                request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                "data": None,
                "flash": [{"level": "danger", "message": e.description}],
                "error": {"code": "BAD_REQUEST", "message": e.description},
                "meta": {}
            }), 400
        flash(e.description, "danger")
        back = request.referrer
        code = 303 if request.method == 'POST' else 302
        return redirect(back, code=code)

    # ─── Middleware / before_request ─────────────────────────────────────────

    @app.before_request
    def _csrf_guard_api():
        """Valida CSRF y gestiona la expiración de sesión."""
        validate_csrf_for_api()

        safe_endpoints = {
            'pages_auth.login_page',
            'pages_auth.register_page',
            'api_auth.api_login',
            'api_auth.api_logout',
            'api_auth.api_keepalive',
            'api_health.health_check',
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
    def check_password_change_required():
        """Fuerza cambio de contraseña si must_change_password=True."""
        if not current_user.is_authenticated:
            return None
        if not getattr(current_user, 'must_change_password', False):
            return None

        allowed_paths = [
            '/api/v1/auth/change-password',
            '/api/v1/auth/logout',
            '/api/v1/auth/me',
            '/api/v1/auth/keepalive',
            '/auth/logout',
            '/static/',
            '/health',
        ]

        for allowed in allowed_paths:
            if request.path.startswith(allowed):
                return None

        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
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

        return None

    @app.context_processor
    def inject_tokens_and_version():
        return {
            "static_version": app.config.get("STATIC_VERSION", "1.0.0"),
            "csrf_token": generate_csrf_token,
        }

    @app.route('/')
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for('pages_auth.login_page'))
        return redirect(url_for('pages_user.dashboard'))

    return app


app = create_app()

"""Infrastructure wiring: reverse proxy, DB engine options and Socket.IO."""
import mimetypes

from werkzeug.middleware.proxy_fix import ProxyFix

# Slim Python images ship without font types: the vendored Bootstrap Icons
# fonts were served as application/octet-stream when Flask serves /static
# itself (dev without nginx, E2E). nginx's mime.types already knows them.
mimetypes.add_type('font/woff2', '.woff2')
mimetypes.add_type('font/woff', '.woff')

from app.extensions import socketio


def socketio_allowed_origins(app):
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


def configure_proxy_fix(app):
    # ProxyFix para manejar headers de proxy reverso (HTTPS)
    if app.config.get('FLASK_ENV') == 'production':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


def configure_engine_options(app):
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


def init_socketio(app):
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
        cors_allowed_origins=socketio_allowed_origins(app),
        logger=False,
        engineio_logger=False,
    )
    from app.sockets import register_socket_handlers
    register_socket_handlers(socketio)

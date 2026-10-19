from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import current_user, LoginManager
from flask_migrate import Migrate
from app.config import Config
from app.utils.csrf import init_csrf

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(test_config=None):
    from app.bootstrap.auth import register_login_manager
    from app.bootstrap.error_handlers import register_error_handlers
    from app.bootstrap.extensions import (
        configure_engine_options, configure_proxy_fix, init_socketio,
    )
    from app.bootstrap.request_hooks import register_request_hooks
    from app.bootstrap.template_context import register_template_context

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

    configure_proxy_fix(app)
    configure_engine_options(app)

    db.init_app(app)

    # Blueprints
    from app.routes.api import register_api_blueprints
    from app.routes.pages import register_page_blueprints
    register_api_blueprints(app)
    register_page_blueprints(app)

    # Inicializar Celery (evita ciclos de importación al no crear otra app)
    from app.celery_app import init_celery
    init_celery(app)

    init_socketio(app)

    register_login_manager(app, login_manager)

    migrate = Migrate(app, db)  # noqa: F841

    register_error_handlers(app, login_manager)

    # ─── Middleware / before_request ─────────────────────────────────────────

    # Registered before every other before_request hook: a forged mutation is
    # rejected before session bookkeeping or authentication run.
    init_csrf(app)
    register_request_hooks(app)
    register_template_context(app)

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

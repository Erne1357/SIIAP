from flask import Flask, session, flash, redirect, url_for, render_template
from flask import request
from flask_sqlalchemy import SQLAlchemy
from flask_login import current_user, logout_user, LoginManager
from flask_migrate import Migrate
from flask_bootstrap import Bootstrap
from datetime import datetime, timezone, timedelta
from app.config import Config
from app.utils.auth import roles_required
from app.utils.csrf import generate_csrf_token, validate_csrf_for_api

db = SQLAlchemy()
login_manager = LoginManager()

def create_app(test_config=None):
     app = Flask(__name__, template_folder='templates', static_folder='static')
     app.config["STATIC_VERSION"] = "1.0.41111111132"  

     Bootstrap(app)

     if test_config is None:
          app.config.from_object(Config)
     else:
          app.config.update(test_config)
     
     db.init_app(app)
     register_blueprints(app)
     # Inicializar y configurar el LoginManager
     login_manager.init_app(app)
     login_manager.login_view = 'pages_auth.login_page'  #  Redirige al login si no está autenticado
     login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."

     migrate = Migrate(app, db)
     

     # Definir el user_loader para Flask-Login
     from app.models.user import User
     @login_manager.user_loader
     def load_user(user_id):
          return User.query.get(int(user_id))
     
     # Configurar duración de la sesión (17 minutos)
     app.permanent_session_lifetime = timedelta(minutes=17)

     @app.errorhandler(404)
     def page_not_found(e):
          return render_template('404.html', error = e), 404
     
     @app.errorhandler(500)
     def internal_server_error(e):
          return render_template('500.html', error = e), 500

     @app.errorhandler(403)
     def forbidden(e):
          flash("No tienes permiso para acceder a esta página.", "danger")
          back = request.referrer
          if not back or back == request.url:
               back = url_for('index')
          code = 303 if request.method == 'POST' else 302
          return redirect(back, code=code)
     
     @app.errorhandler(400)
     def bad_request(e):
          flash(e.description, "danger")
          back = request.referrer
          code = 303 if request.method == 'POST' else 302
          return redirect(back, code=code)

     @app.before_request
     def _csrf_guard_api():
          validate_csrf_for_api()  # protege la API con token

     @app.context_processor
     def inject_tokens_and_version():
          return {
               "static_version": app.config.get("STATIC_VERSION", "1.0.0"),
               "csrf_token": generate_csrf_token,    # {{ csrf_token() }} en templates
          }
     
     @app.route('/')
     def index():
          if not current_user.is_authenticated:
               return redirect(url_for('pages_auth.login_page'))
          return redirect(url_for('user.dashboard'))
     
     
     return app

def register_blueprints(app):
     #Registrarr apis
     from app.routes.api.auth_api import api_auth_bp
     app.register_blueprint(api_auth_bp)

     #Registrar páginas
     from app.routes.pages.auth import pages_auth
     app.register_blueprint(pages_auth)
     # Registrar blueprints
     #from app.routes.auth import auth as auth_blueprint
     from app.routes.user import user as user_blueprint
     from app.routes.program.program import program_bp as program_blueprint
     from app.routes.files import bp_files as files_blueprint
     from app.routes.admin.admin import admin_bp as admin_blueprint
     #app.register_blueprint(auth_blueprint)  
     app.register_blueprint(user_blueprint, url_prefix='/user')
     app.register_blueprint(program_blueprint, url_prefix='/programs')
     app.register_blueprint(files_blueprint, url_prefix='/files')
     app.register_blueprint(admin_blueprint)


app = create_app()

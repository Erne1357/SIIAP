from flask import Flask, jsonify, session, flash, redirect, url_for, render_template
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
     Bootstrap(app)

     if test_config is None:
          app.config.from_object(Config)
     else:
          app.config.update(test_config)
     
     db.init_app(app)
     register_blueprints(app)
     
     # Inicializar y configurar el LoginManager
     login_manager.init_app(app)
     login_manager.login_view = 'pages_auth.login_page'
     login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
     login_manager.login_message_category = "warning"

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
          """Valida CSRF y gestiona la expiración de sesión"""
          validate_csrf_for_api()
          
          # Endpoints que NO requieren validación de sesión
          safe_endpoints = {
               'pages_auth.login_page',
               'pages_auth.register_page',
               'api_auth.api_login',
               'api_auth.api_logout',
               'api_auth.api_keepalive',
               'static',
          }
          
          # Si el endpoint actual es seguro, no validar sesión
          if request.endpoint in safe_endpoints:
               return

          # Hacer la sesión permanente
          session.permanent = True
          now_ts = datetime.now(timezone.utc).timestamp()
          last_activity = session.get('last_activity')

          # Solo validar expiración si el usuario está autenticado
          if current_user.is_authenticated:
               if last_activity:
                    # Verificar si han pasado más de 15 minutos
                    if now_ts - last_activity > 15 * 60:  # 15 min
                         # Limpiar la sesión completamente
                         session.clear()
                         logout_user()
                         flash("Tu sesión ha expirado por inactividad.", "warning")
                         return redirect(url_for('pages_auth.login_page'))
               
               # Actualizar la última actividad
               session['last_activity'] = now_ts

     @app.before_request
     def check_password_change_required():
          """
          Middleware que verifica si el usuario debe cambiar su contraseña.
          Si must_change_password=True, solo permite acceso a:
          - Endpoints de cambio de contraseña
          - Endpoint de logout
          - Archivos estáticos
          - Páginas de autenticación (login, registro)

          Cualquier otra ruta será bloqueada con 403.
          """
          # Ignorar si no está autenticado
          if not current_user.is_authenticated:
               return None

          # Verificar si debe cambiar contraseña
          if not hasattr(current_user, 'must_change_password'):
               return None

          if not current_user.must_change_password:
               return None

          # Lista de rutas permitidas cuando debe cambiar contraseña
          allowed_paths = [
               '/api/v1/auth/change-password',
               '/api/v1/auth/logout',
               '/api/v1/auth/me',
               '/api/v1/auth/keepalive',
               '/auth/logout',
               '/static/',  # Archivos estáticos
          ]

          # Verificar si la ruta actual está permitida
          current_path = request.path

          for allowed in allowed_paths:
               if current_path.startswith(allowed):
                    return None

          # Si es una petición AJAX (JSON), retornar error JSON
          if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
               return jsonify({
                    "data": None,
                    "flash": [{
                         "level": "warning",
                         "message": "Debes cambiar tu contraseña antes de continuar"
                    }],
                    "error": {
                         "code": "PASSWORD_CHANGE_REQUIRED",
                         "message": "Cambio de contraseña obligatorio",
                         "must_change_password": True
                    },
                    "meta": {}
               }), 403

          # Si es una petición normal, no hacemos nada (el modal se encargará)
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

def register_blueprints(app):
     # Registrar apis
     from app.routes.api.auth_api import api_auth_bp
     from app.routes.api.programs_api import api_programs
     from app.routes.api.admission_api import api_admission
     from app.routes.api.submissions_api import api_submissions
     from app.routes.api.files_api import api_files
     from app.routes.api.users_api import api_users
     from app.routes.api.admin.review_api import api_review
     from app.routes.api.extensions_api import api_extensions
     from app.routes.api.events_api import api_events
     from app.routes.api.appointments_api import api_appointments
     from app.routes.api.program_changes_api import api_program_changes
     from app.routes.api.retention_api import api_retention
     from app.routes.api.archives_api import api_archives
     from app.routes.api.coordinator_api import api_coordinator
     from app.routes.api.attendance_api import api_attendance
     from app.routes.api.invitations_api import api_invitations
     from app.routes.api.interviews_api import api_interviews
     
     app.register_blueprint(api_auth_bp)
     app.register_blueprint(api_programs)
     app.register_blueprint(api_admission)
     app.register_blueprint(api_submissions)
     app.register_blueprint(api_files)
     app.register_blueprint(api_users)
     app.register_blueprint(api_review)
     app.register_blueprint(api_extensions)
     app.register_blueprint(api_events)
     app.register_blueprint(api_appointments)
     app.register_blueprint(api_program_changes)
     app.register_blueprint(api_retention)
     app.register_blueprint(api_archives)
     app.register_blueprint(api_coordinator)
     app.register_blueprint(api_attendance)
     app.register_blueprint(api_invitations)
     app.register_blueprint(api_interviews)

     # Registrar páginas
     from app.routes.pages.auth import pages_auth
     from app.routes.pages.programs_pages import program_bp
     from app.routes.pages.users_pages import pages_user
     from app.routes.pages.admin.admin_pages import pages_admin
     from app.routes.pages.coordinator_pages import pages_coordinator
     from app.routes.pages.event_pages import pages_events_public
     
     app.register_blueprint(pages_auth)
     app.register_blueprint(program_bp)
     app.register_blueprint(pages_user)
     app.register_blueprint(pages_admin)
     app.register_blueprint(pages_coordinator)
     app.register_blueprint(pages_events_public)

app = create_app()
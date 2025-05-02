from flask import Flask, session, flash, redirect, url_for, render_template
from flask import request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import current_user, logout_user, LoginManager
from flask_migrate import Migrate
from flask_bootstrap import Bootstrap
from datetime import datetime, timezone, timedelta
from app.config import Config

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
     
     # Inicializar y configurar el LoginManager
     login_manager.init_app(app)
     login_manager.login_view = 'auth.login'  #  Redirige al login si no está autenticado
     login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."

     migrate = Migrate(app, db)
     

     # Definir el user_loader para Flask-Login
     from app.models.user import User
     @login_manager.user_loader
     def load_user(user_id):
          return User.query.get(int(user_id))
     
     # Configurar duración de la sesión (15 minutos)
     app.permanent_session_lifetime = timedelta(minutes=15)

     @app.errorhandler(404)
     def page_not_found(e):
          return render_template('404.html', error = e), 404

     
     @app.before_request
     def session_management():
          session.permanent = True
          now_ts = datetime.now(timezone.utc).timestamp()
          last_activity = session.get('last_activity')
          if current_user.is_authenticated and last_activity:
               if now_ts - last_activity > 15 * 60:  # 15 minutos en segundos
                    flash("Tu sesión ha expirado por inactividad.", "warning")
                    logout_user()
                    return redirect(url_for('auth.login'))
          session['last_activity'] = now_ts
          
     
     
     # Registrar blueprints
     from app.routes.auth import auth as auth_blueprint
     from app.routes.user import user as user_blueprint
     app.register_blueprint(auth_blueprint)  
     app.register_blueprint(user_blueprint, url_prefix='/user')
     
     @app.route('/')
     def index():
          if not current_user.is_authenticated:
               return redirect(url_for('auth.login'))
          return redirect(url_for('user.dashboard'))
     
          
     return app

app = create_app()

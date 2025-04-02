from flask import Flask, redirect, url_for
from app.config import Config
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)
    
    db.init_app(app)
    
    # Importar Blueprints
    from app.routes.auth import auth as auth_blueprint
    #from app.routes.admin import admin as admin_blueprint
    from app.routes.user import user as user_blueprint
    #from app.routes.test import test_bp as test_blueprint

    # Registrar Blueprints con prefijos
    app.register_blueprint(auth_blueprint)
    #app.register_blueprint(admin_blueprint, url_prefix='/admin')
    app.register_blueprint(user_blueprint, url_prefix='/user')
    #app.register_blueprint(test_blueprint, url_prefix='/test')

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))
    
    return app

app = create_app()

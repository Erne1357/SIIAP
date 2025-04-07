from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from werkzeug.security import check_password_hash
from app.models.user import User

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Obtiene datos del formulario
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Consulta el usuario en la base de datos
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            # Registra la actividad inicial de la sesión (timestamp en segundos)
            session['last_activity'] = datetime.utcnow().timestamp()
            flash("Inicio de sesión exitoso", "success")
            return redirect(url_for('user.dashboard'))
        else:
            flash("Credenciales incorrectas", "danger")
    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión", "info")
    return redirect(url_for('auth.login'))

@auth.route('/keepalive')
@login_required
def keepalive():
    # Actualiza la marca de actividad para prolongar la sesión
    session['last_activity'] = datetime.utcnow().timestamp()
    return "OK", 200

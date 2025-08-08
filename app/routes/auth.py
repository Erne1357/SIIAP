from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
from app.models.user import User
from app.models.role import Role
from app import db

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
            session['last_activity'] = datetime.now(timezone.utc).timestamp()
            # Actualiza la fecha de último inicio de sesión
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            flash("Inicio de sesión exitoso", "success")
            
            return redirect(url_for('user.dashboard'))
        else:
            flash("Credenciales incorrectas", "danger")
    else:
        if current_user.is_authenticated:
            return redirect(url_for('index'))
    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    session.pop('_flashes', None)  # Limpiar mensajes de flash
    logout_user()
    flash("Has cerrado sesión ", "info")
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Recoger y limpiar datos del formulario
        first_name = request.form.get('first_name').strip()
        last_name = request.form.get('last_name').strip()
        mother_last_name = request.form.get('mother_last_name').strip() if request.form.get('mother_last_name') else None
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        is_internal = request.form.get('is_internal') == 'on'  # Convertir a booleano
        
        # Validación: Contraseñas coinciden
        if password != confirm_password:
            flash("Las contraseñas no coinciden.", "danger")
            return render_template('auth/register.html')
        
        # Validación: Verificar unicidad de username y email
        if User.query.filter_by(username=username).first():
            flash("El nombre de usuario ya existe.", "danger")
            return render_template('auth/register.html')
        if User.query.filter_by(email=email).first():
            flash("El correo electrónico ya está registrado.", "danger")
            return render_template('auth/register.html')
        
        # Buscar el rol "applicant". 
        # Se asume que éste ya existe en la base de datos. Si no, se debe crearlo manualmente.
        applicant_role = Role.query.filter_by(name='applicant').first()
        if not applicant_role:
            flash("No se encontró el rol 'applicant'. Contacta al administrador.", "danger")
            return render_template('auth/register.html')
        
        # Crear el usuario
        new_user = User(
            first_name, 
            last_name, 
            mother_last_name, 
            username, 
            password, 
            email, 
            is_internal,
            applicant_role.id,
            avatar='default.jpg'  # Asignar un avatar por defecto
        )
        db.session.add(new_user)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash("Error al registrar el usuario: ", "danger")
            return render_template('auth/register.html')
        
        flash("Registro exitoso. Ahora inicia sesión.", "success")
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth.route('/keepalive')
@login_required
def keepalive():
    # Actualiza la marca de actividad para prolongar la sesión
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return "Unauthorized", 401

    session['last_activity'] = datetime.now(timezone.utc).timestamp()
    return "OK", 200

# app/routes/api/auth_api.py
from flask import Blueprint, request, jsonify, session, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timezone
from werkzeug.security import check_password_hash, generate_password_hash
from app.models.user import User
from app import db
import re

api_auth_bp = Blueprint("api_auth", __name__, url_prefix="/api/v1/auth")

# Contraseña por defecto del sistema
DEFAULT_PASSWORD = "tecno#2K"

def validate_password_strength(password):
    """
    Valida la fortaleza de la contraseña.
    Requisitos:
    - Mínimo 8 caracteres
    - Al menos una mayúscula
    - Al menos una minúscula
    - Al menos un número
    - Al menos un caracter especial
    """
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres"
    
    if not re.search(r'[A-Z]', password):
        return False, "La contraseña debe contener al menos una letra mayúscula"
    
    if not re.search(r'[a-z]', password):
        return False, "La contraseña debe contener al menos una letra minúscula"
    
    if not re.search(r'\d', password):
        return False, "La contraseña debe contener al menos un número"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "La contraseña debe contener al menos un caracter especial (!@#$%^&*...)"
    
    return True, "Contraseña válida"


@api_auth_bp.post("/login")
def api_login():
    """
    Login de usuario.
    Verifica si el usuario debe cambiar su contraseña.
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not check_password_hash(user.password, password):
        return jsonify({
            "data": None, 
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Usuario o contraseña inválidos"
            },
            "meta": {}
        }), 401

    login_user(user)
    session['last_activity'] = datetime.now().timestamp()
    user.last_login = datetime.now()
    db.session.commit()

    # NUEVO: Verificar si debe cambiar contraseña
    response_data = {
        "id": user.id, 
        "username": user.username, 
        "role": getattr(getattr(user, "role", None), "name", None),
        "must_change_password": user.must_change_password  # Flag importante
    }

    return jsonify({
        "data": response_data, 
        "error": None, 
        "meta": {}
    }), 200


@api_auth_bp.post("/change-password")
@login_required
def change_password():
    """
    Cambia la contraseña del usuario actual.
    
    JSON esperado:
        - current_password: str (contraseña actual)
        - new_password: str (nueva contraseña)
        - confirm_password: str (confirmación de nueva contraseña)
    
    Validaciones:
        - Contraseña actual correcta
        - Nueva contraseña cumple requisitos de seguridad
        - Nueva contraseña != contraseña por defecto
        - Nueva y confirmación coinciden
    """
    data = request.get_json(silent=True) or {}
    
    current_password = data.get("current_password", "").strip()
    new_password = data.get("new_password", "").strip()
    confirm_password = data.get("confirm_password", "").strip()
    
    # Validación 1: Todos los campos requeridos
    if not all([current_password, new_password, confirm_password]):
        return jsonify({
            "data": None,
            "flash": [{
                "level": "danger",
                "message": "Todos los campos son obligatorios"
            }],
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Campos requeridos faltantes"
            },
            "meta": {}
        }), 400
    
    # Validación 2: Contraseña actual correcta
    if not check_password_hash(current_user.password, current_password):
        return jsonify({
            "data": None,
            "flash": [{
                "level": "danger",
                "message": "La contraseña actual es incorrecta"
            }],
            "error": {
                "code": "INVALID_PASSWORD",
                "message": "Contraseña actual incorrecta"
            },
            "meta": {}
        }), 401
    
    # Validación 3: Nueva contraseña no puede ser la contraseña por defecto
    if new_password == DEFAULT_PASSWORD:
        return jsonify({
            "data": None,
            "flash": [{
                "level": "danger",
                "message": "No puedes usar la contraseña por defecto del sistema"
            }],
            "error": {
                "code": "INVALID_PASSWORD",
                "message": "Contraseña no permitida"
            },
            "meta": {}
        }), 400
    
    # Validación 4: Nueva contraseña y confirmación coinciden
    if new_password != confirm_password:
        return jsonify({
            "data": None,
            "flash": [{
                "level": "danger",
                "message": "Las contraseñas no coinciden"
            }],
            "error": {
                "code": "PASSWORD_MISMATCH",
                "message": "Las contraseñas no coinciden"
            },
            "meta": {}
        }), 400
    
    # Validación 5: Fortaleza de la contraseña
    is_valid, message = validate_password_strength(new_password)
    if not is_valid:
        return jsonify({
            "data": None,
            "flash": [{
                "level": "danger",
                "message": message
            }],
            "error": {
                "code": "WEAK_PASSWORD",
                "message": message
            },
            "meta": {}
        }), 400
    
    # Validación 6: Nueva contraseña diferente a la actual
    if check_password_hash(current_user.password, new_password):
        return jsonify({
            "data": None,
            "flash": [{
                "level": "warning",
                "message": "La nueva contraseña debe ser diferente a la actual"
            }],
            "error": {
                "code": "SAME_PASSWORD",
                "message": "Contraseña idéntica a la actual"
            },
            "meta": {}
        }), 400
    
    # Todo OK, cambiar contraseña
    current_user.password = generate_password_hash(new_password)
    current_user.must_change_password = False  # Ya cambió su contraseña
    db.session.commit()
    
    return jsonify({
        "data": {
            "user_id": current_user.id,
            "username": current_user.username,
            "password_changed": True
        },
        "flash": [{
            "level": "success",
            "message": "¡Contraseña cambiada exitosamente!"
        }],
        "error": None,
        "meta": {
            "must_change_password": False
        }
    }), 200


@api_auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def api_logout():
    """
    - GET: permite usar <a href="..."> para cerrar sesión y redirigir a /login
    - POST: usado por JS (session timeout) => responde JSON
    """
    session.pop('_flashes', None)
    logout_user()
    session.pop('last_activity', None)

    if request.method == 'GET':
        return redirect(url_for('pages_auth.login_page'))

    return jsonify({
        "data": None,
        "flash": [{"level": "info", "message": "Has cerrado sesión."}],
        "error": None, 
        "meta": {}
    }), 200


@api_auth_bp.get("/me")
@login_required
def api_me():
    """
    Obtiene información del usuario actual.
    Incluye el flag must_change_password.
    """
    u = current_user
    return jsonify({
        "data": {
            "id": u.id, 
            "username": u.username, 
            "email": u.email,
            "first_name": u.first_name, 
            "last_name": u.last_name,
            "role": getattr(getattr(u, "role", None), "name", None),
            "must_change_password": u.must_change_password
        }, 
        "error": None, 
        "meta": {}
    }), 200


@api_auth_bp.get("/keepalive")
@login_required
def api_keepalive():
    """Mantiene la sesión activa"""
    session['last_activity'] = datetime.now().timestamp()
    return jsonify({
        "data": "OK", 
        "error": None, 
        "meta": {}
    }), 200
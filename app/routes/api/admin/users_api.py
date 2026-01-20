# app/routes/api/admin/users_admin_api.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.user_history import UserHistory
from app.models.program import Program
from app.models.user_program import UserProgram
from app.services.user_history_service import UserHistoryService
from app.utils.auth import roles_required
from werkzeug.security import generate_password_hash
from app.utils.datetime_utils import now_local
import json
import re

api_admin_users = Blueprint("api_admin_users", __name__, url_prefix="/api/v1/admin/users")

def _sanitize(s: str | None) -> str | None:
    """Sanitiza strings eliminando espacios y retornando None si está vacío"""
    if s is None: 
        return None
    s = s.strip()
    return s or None


@api_admin_users.get("/")
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def list_users():
    """Lista usuarios con filtros opcionales"""
    # Parámetros de paginación
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Filtros
    role_filter = request.args.get('role', type=str)
    program_filter = request.args.get('program', type=int)
    active_filter = request.args.get('active', 'all', type=str)
    search = request.args.get('search', type=str)
    
    # Query base
    query = User.query
    
    # Filtro por rol
    if role_filter:
        from app.models.role import Role
        query = query.join(User.role).filter(Role.name == role_filter)
    
    # Filtro por programa
    if program_filter:
        query = query.join(UserProgram).filter(UserProgram.program_id == program_filter)
    
    # Filtro por estado activo
    if active_filter == 'true':
        query = query.filter(User.is_active == True)
    elif active_filter == 'false':
        query = query.filter(User.is_active == False)
    
    # Búsqueda por texto
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                User.first_name.ilike(search_pattern),
                User.last_name.ilike(search_pattern),
                User.mother_last_name.ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.username.ilike(search_pattern),
                User.control_number.ilike(search_pattern)
            )
        )
    
    # Ejecutar query con paginación
    pagination = query.order_by(User.last_name, User.first_name).paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )

    users_data = [user.to_dict(include_sensitive=True) for user in pagination.items]

    return jsonify({
        "data": {
            "users": users_data,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev
            }
        },
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.get("/<int:user_id>")
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def get_user(user_id):
    """Obtiene información detallada de un usuario específico"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Usuario no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Usuario no existe"},
            "meta": {}
        }), 404
    
    # Obtener historial
    history_entries = UserHistoryService.get_user_history(user_id=user_id, limit=50)
    
    # Obtener programa
    user_program = UserProgram.query.filter_by(user_id=user_id).first()
    
    return jsonify({
        "data": {
            "user": user.to_dict(include_sensitive=True),
            "program": {
                "id": user_program.program.id,
                "name": user_program.program.name,
                "slug": user_program.program.slug
            } if user_program else None,
            "history": [entry.to_dict() for entry in history_entries]
        },
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.patch("/<int:user_id>")
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def update_user(user_id):
    """Actualiza información básica del usuario"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Usuario no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Usuario no existe"},
            "meta": {}
        }), 404
    
    payload = request.get_json(silent=True) or {}
    changed_fields = {}
    
    # Actualizar campos
    if 'first_name' in payload:
        new_value = _sanitize(payload['first_name'])
        if new_value and new_value != user.first_name:
            changed_fields['first_name'] = {'old': user.first_name, 'new': new_value}
            user.first_name = new_value
    
    if 'last_name' in payload:
        new_value = _sanitize(payload['last_name'])
        if new_value and new_value != user.last_name:
            changed_fields['last_name'] = {'old': user.last_name, 'new': new_value}
            user.last_name = new_value
    
    if 'mother_last_name' in payload:
        new_value = _sanitize(payload['mother_last_name'])
        if new_value != user.mother_last_name:
            changed_fields['mother_last_name'] = {'old': user.mother_last_name, 'new': new_value}
            user.mother_last_name = new_value
    
    if 'email' in payload:
        new_value = _sanitize(payload['email'])
        if new_value and new_value != user.email:
            existing = User.query.filter(User.email == new_value, User.id != user_id).first()
            if existing:
                return jsonify({
                    "data": None,
                    "flash": [{"level": "danger", "message": "El email ya está en uso."}],
                    "error": {"code": "VALIDATION", "message": "Email duplicado"},
                    "meta": {}
                }), 400
            changed_fields['email'] = {'old': user.email, 'new': new_value}
            user.email = new_value
    
    # Registrar cambios
    if changed_fields:
        UserHistoryService.log_basic_info_update(user_id=user_id, changed_fields=changed_fields)
    
    db.session.commit()
    
    return jsonify({
        "data": {"user": user.to_dict(include_sensitive=True)},
        "flash": [{"level": "success", "message": "Usuario actualizado correctamente."}],
        "error": None,
        "meta": {"changed_fields": list(changed_fields.keys())}
    }), 200

# ESTA ES LA CONTINUACIÓN - PEGAR DESPUÉS DE LA PARTE 1

@api_admin_users.post("/<int:user_id>/reset-password")
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def reset_password(user_id):
    """Resetea la contraseña del usuario a 'tecno#2K'"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Usuario no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Usuario no existe"},
            "meta": {}
        }), 404
    
    # No permitir resetear la propia contraseña
    if user_id == current_user.id:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No puedes resetear tu propia contraseña."}],
            "error": {"code": "FORBIDDEN", "message": "Acción no permitida"},
            "meta": {}
        }), 403
    
    # Resetear contraseña
    user.password = generate_password_hash('tecno#2K')
    user.must_change_password = True
    
    # Registrar en historial
    UserHistoryService.log_password_reset(user_id=user_id)
    
    db.session.commit()
    
    return jsonify({
        "data": None,
        "flash": [{"level": "success", "message": f"Contraseña reseteada para {user.first_name} {user.last_name}."}],
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.patch("/<int:user_id>/toggle-active")
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def toggle_active(user_id):
    """Activa o desactiva un usuario"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Usuario no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Usuario no existe"},
            "meta": {}
        }), 404
    
    # No permitir desactivarse a sí mismo
    if user_id == current_user.id:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No puedes desactivarte a ti mismo."}],
            "error": {"code": "FORBIDDEN", "message": "Acción no permitida"},
            "meta": {}
        }), 403
    
    # Toggle estado
    user.is_active = not user.is_active
    action = 'activated' if user.is_active else 'deactivated'
    message = f"Usuario {user.first_name} {user.last_name} {'activado' if user.is_active else 'desactivado'}."
    
    # Registrar en historial
    UserHistoryService.log_user_activation(user_id=user_id, is_active=user.is_active)
    
    db.session.commit()
    
    return jsonify({
        "data": {"is_active": user.is_active},
        "flash": [{"level": "success", "message": message}],
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.post("/<int:user_id>/assign-control-number")
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def assign_control_number(user_id):
    """Asigna un número de control al usuario"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Usuario no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Usuario no existe"},
            "meta": {}
        }), 404
    
    payload = request.get_json(silent=True) or {}
    control_number = _sanitize(payload.get('control_number'))
    
    if not control_number:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Número de control es requerido."}],
            "error": {"code": "VALIDATION", "message": "Campo requerido"},
            "meta": {}
        }), 400
    
    # Validar formato: M o D seguido de 8 dígitos
    if not re.match(r'^[MD]\d{8}$', control_number):
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Formato inválido. Debe ser M o D seguido de 8 dígitos."}],
            "error": {"code": "VALIDATION", "message": "Formato inválido"},
            "meta": {}
        }), 400
    
    # Verificar que no exista
    existing = User.query.filter(User.control_number == control_number).first()
    if existing:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": f"El número de control {control_number} ya está asignado."}],
            "error": {"code": "VALIDATION", "message": "Número de control duplicado"},
            "meta": {}
        }), 400
    
    # Verificar que tenga programa
    user_program = UserProgram.query.filter_by(user_id=user_id).first()
    if not user_program:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "El usuario debe tener un programa asignado primero."}],
            "error": {"code": "VALIDATION", "message": "Sin programa asignado"},
            "meta": {}
        }), 400
    
    # Validar tipo de programa
    program_type = control_number[0]
    program_name = user_program.program.name.lower()
    
    if program_type == 'M' and 'maestr' not in program_name:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "El número debe comenzar con 'M' para maestrías."}],
            "error": {"code": "VALIDATION", "message": "Tipo no coincide"},
            "meta": {}
        }), 400
    elif program_type == 'D' and 'doctor' not in program_name:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "El número debe comenzar con 'D' para doctorados."}],
            "error": {"code": "VALIDATION", "message": "Tipo no coincide"},
            "meta": {}
        }), 400
    
    # Asignar
    old_username = user.username
    user.username = control_number
    user.control_number = control_number
    user.control_number_assigned_at = now_local()
    
    # Registrar
    UserHistoryService.log_control_number_assignment(
        user_id=user_id,
        control_number=control_number,
        old_username=old_username,
        program_name=user_program.program.name
    )
    
    db.session.commit()
    
    return jsonify({
        "data": {"control_number": control_number, "username": user.username},
        "flash": [{"level": "success", "message": f"Número de control {control_number} asignado."}],
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.delete("/<int:user_id>")
@login_required
@roles_required('postgraduate_admin')
def delete_user(user_id):
    """Elimina un usuario (solo admin general)"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Usuario no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Usuario no existe"},
            "meta": {}
        }), 404
    
    # No permitir eliminarse a sí mismo
    if user_id == current_user.id:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No puedes eliminarte a ti mismo."}],
            "error": {"code": "FORBIDDEN", "message": "Acción no permitida"},
            "meta": {}
        }), 403
    
    payload = request.get_json(silent=True) or {}
    force = payload.get('force', False)
    
    # Verificar datos relacionados
    has_submissions = len(user.submissions) > 0
    
    if has_submissions and not force:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": "El usuario tiene documentos. Usa 'force=true' para eliminar."}],
            "error": {"code": "VALIDATION", "message": "Usuario tiene datos relacionados"},
            "meta": {"has_submissions": True}
        }), 400
    
    # Registrar eliminación
    user_name = f"{user.first_name} {user.last_name}"
    UserHistoryService.log_user_deletion(user_id=user_id, user_name=user_name)
    
    db.session.commit()
    
    # Eliminar usuario
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({
        "data": None,
        "flash": [{"level": "success", "message": f"Usuario {user_name} eliminado."}],
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.get("/<int:user_id>/history")
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def user_history(user_id):
    """Obtiene el historial completo de un usuario"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Usuario no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Usuario no existe"},
            "meta": {}
        }), 404
    
    history_entries = UserHistoryService.get_user_history(user_id=user_id)
    
    return jsonify({
        "data": {
            "user": {"id": user.id, "name": f"{user.first_name} {user.last_name}"},
            "history": [entry.to_dict() for entry in history_entries]
        },
        "error": None,
        "meta": {"total": len(history_entries)}
    }), 200
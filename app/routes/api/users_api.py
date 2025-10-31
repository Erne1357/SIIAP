# app/routes/api/users_api.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from datetime import datetime

from app.models.user_history import UserHistory

api_users = Blueprint("api_users", __name__, url_prefix="/api/v1/users")

def _sanitize(s: str | None) -> str | None:
    if s is None: 
        return None
    s = s.strip()
    return s or None

@api_users.get("/me")
@login_required
def me():
    u = current_user
    data = {
        "id": u.id,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "mother_last_name": u.mother_last_name,
        "username": u.username,
        "email": u.email,
        "is_internal": u.is_internal,
        "scolarship_type": u.scolarship_type,
        "role": u.role.name if u.role else None,
        "avatar_url": u.avatar_url,
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "registration_date": u.registration_date.isoformat() if u.registration_date else None,
        "profile_completed": u.profile_completed,
    }
    return jsonify({"data": {"user": data}, "error": None, "meta": {}}), 200

@api_users.patch("/me/complete-profile")
@login_required
def complete_profile():
    """
    Actualiza la información completa del perfil del usuario.
    Todos los campos adicionales que determinan si el perfil está "completo".
    """
    payload = request.get_json(silent=True) or {}
    
    # Campos de información personal
    current_user.phone = _sanitize(payload.get("phone"))
    current_user.mobile_phone = _sanitize(payload.get("mobile_phone"))
    current_user.address = _sanitize(payload.get("address"))
    current_user.curp = _sanitize(payload.get("curp"))
    current_user.rfc = _sanitize(payload.get("rfc"))
    current_user.birth_place = _sanitize(payload.get("birth_place"))
    current_user.cedula_profesional = _sanitize(payload.get("cedula_profesional"))
    current_user.nss = _sanitize(payload.get("nss"))
    
    # Fecha de nacimiento (requiere manejo especial)
    birth_date_str = payload.get("birth_date")
    if birth_date_str:
        try:
            current_user.birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({
                "data": None,
                "flash": [{"level": "danger", "message": "Formato de fecha de nacimiento inválido."}],
                "error": {"code": "VALIDATION", "message": "Fecha inválida"},
                "meta": {}
            }), 400
    
    # Contacto de emergencia
    current_user.emergency_contact_name = _sanitize(payload.get("emergency_contact_name"))
    current_user.emergency_contact_phone = _sanitize(payload.get("emergency_contact_phone"))
    current_user.emergency_contact_relationship = _sanitize(payload.get("emergency_contact_relationship"))
    
    # Actualizar automáticamente el estado de perfil completo
    was_complete_before = current_user.profile_completed
    is_complete_now = current_user.update_profile_completion_status()
    
    db.session.commit()
    
    # Mensaje diferente si acaba de completar el perfil
    if not was_complete_before and is_complete_now:
        flash_message = "¡Perfil completado exitosamente! Ahora eres elegible para entrevistas."
        flash_level = "success"
    elif is_complete_now:
        flash_message = "Información del perfil actualizada correctamente."
        flash_level = "success"
    else:
        flash_message = "Información guardada. Completa todos los campos requeridos para finalizar tu perfil."
        flash_level = "warning"
    
    return jsonify({
        "data": {
            "profile_completed": is_complete_now,
            "was_completed_before": was_complete_before,
            "newly_completed": not was_complete_before and is_complete_now
        },
        "flash": [{"level": flash_level, "message": flash_message}],
        "error": None,
        "meta": {"completion_status_changed": was_complete_before != is_complete_now}
    }), 200

@api_users.get("/me/profile-completion")
@login_required
def profile_completion_status():
    """
    Obtiene el estado detallado de completitud del perfil.
    """
    required_fields = {
        "phone_or_mobile": bool(current_user.phone or current_user.mobile_phone),
        "address": bool(current_user.address and current_user.address.strip()),
        "curp": bool(current_user.curp and current_user.curp.strip()),
        "birth_date": bool(current_user.birth_date),
        "emergency_contact_name": bool(current_user.emergency_contact_name and current_user.emergency_contact_name.strip()),
        "emergency_contact_phone": bool(current_user.emergency_contact_phone and current_user.emergency_contact_phone.strip()),
        "emergency_contact_relationship": bool(current_user.emergency_contact_relationship and current_user.emergency_contact_relationship.strip())
    }
    
    completed_count = sum(required_fields.values())
    total_count = len(required_fields)
    completion_percentage = (completed_count / total_count) * 100
    
    return jsonify({
        "data": {
            "profile_completed": current_user.profile_completed,
            "completion_percentage": completion_percentage,
            "required_fields_status": required_fields,
            "completed_count": completed_count,
            "total_count": total_count,
            "missing_fields": [field for field, completed in required_fields.items() if not completed]
        },
        "error": None,
        "meta": {}
    }), 200

# Actualizar el método update_me existente para que también verifique el perfil:
@api_users.patch("/me")
@login_required  
def update_me():
    """
    JSON:
      - first_name (str, req)
      - last_name (str, req)
      - mother_last_name (str, opt)
      - scolarship_type (str, opt)
    """
    payload = request.get_json(silent=True) or {}
    first = _sanitize(payload.get("first_name"))
    last  = _sanitize(payload.get("last_name"))
    mother = _sanitize(payload.get("mother_last_name"))
    scol  = _sanitize(payload.get("scolarship_type"))

    if not first or not last:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Nombre y Apellido Paterno son obligatorios."}],
            "error": {"code": "VALIDATION", "message": "Campos requeridos faltantes"},
            "meta": {}
        }), 400

    current_user.first_name = first
    current_user.last_name = last
    current_user.mother_last_name = mother
    if scol is not None:
        current_user.scolarship_type = scol

    # Actualizar estado de perfil completo
    current_user.update_profile_completion_status()

    db.session.commit()

    return jsonify({
        "data": {"user": {
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "mother_last_name": current_user.mother_last_name,
            "scolarship_type": current_user.scolarship_type,
            "profile_completed": current_user.profile_completed
        }},
        "flash": [{"level": "success", "message": "Perfil actualizado correctamente."}],
        "error": None, "meta": {}
    }), 200

@api_users.get("/me/history")
@login_required
def user_history():
    """
    Obtiene el historial de cambios del usuario.
    """
    history = UserHistory.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "data": {
            "history": [entry.to_dict() for entry in history]
        },
        "error": None,
        "meta": {}
    }), 200
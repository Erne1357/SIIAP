# app/routes/api/users_api.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db

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
    }
    return jsonify({"data": {"user": data}, "error": None, "meta": {}}), 200

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

    db.session.commit()

    return jsonify({
        "data": {"user": {
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "mother_last_name": current_user.mother_last_name,
            "scolarship_type": current_user.scolarship_type,
        }},
        "flash": [{"level": "success", "message": "Perfil actualizado correctamente."}],
        "error": None, "meta": {}
    }), 200

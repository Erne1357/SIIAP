# app/routes/api/auth_api.py
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
from app.models.user import User
from app import db

api_auth_bp = Blueprint("api_auth", __name__, url_prefix="/api/v1/auth")

@api_auth_bp.post("/login")
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"data": None, "error": {"code":"INVALID_CREDENTIALS","message":"Usuario o contraseña inválidos"}}), 401

    login_user(user)
    session['last_activity'] = datetime.now(timezone.utc).timestamp()
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({"data": {"id": user.id, "username": user.username, "role": getattr(getattr(user,"role",None),"name",None)}, "error": None, "meta": {}}), 200

@api_auth_bp.post("/logout")
@login_required
def api_logout():
    logout_user()
    # limpiar flashes (opcional)
    session.pop('_flashes', None)
    return jsonify({"data": True, "error": None, "meta": {}}), 200

@api_auth_bp.get("/me")
@login_required
def api_me():
    u = current_user
    return jsonify({"data": {
        "id": u.id, "username": u.username, "email": u.email,
        "first_name": u.first_name, "last_name": u.last_name,
        "role": getattr(getattr(u,"role",None),"name",None)
    }, "error": None, "meta": {}}), 200

@api_auth_bp.get("/keepalive")
@login_required
def api_keepalive():
    session['last_activity'] = datetime.now(timezone.utc).timestamp()
    return jsonify({"data": "OK", "error": None, "meta": {}}), 200

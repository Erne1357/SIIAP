# app/routes/pages/auth.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone
from app.models.user import User
from app.models.role import Role
from app import db

pages_auth = Blueprint("pages_auth", __name__)

@pages_auth.route("/login", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        # si ya está logueado, llévalo a su dashboard
        return redirect(url_for("user.dashboard"))
    return render_template("auth/login.html")

@pages_auth.route("/register", methods=["GET", "POST"])
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for("user.dashboard"))

    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name  = (request.form.get("last_name") or "").strip()
        mother_last_name = (request.form.get("mother_last_name") or "").strip() or None
        username = (request.form.get("username") or "").strip()
        email    = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        confirm  = request.form.get("confirm_password") or ""
        is_internal = request.form.get("is_internal") == "on"

        # Validaciones básicas
        if not first_name or not last_name or not username or not email or not password:
            flash("Faltan campos obligatorios.", "danger")
            return render_template("auth/register.html")
        if password != confirm:
            flash("Las contraseñas no coinciden.", "danger")
            return render_template("auth/register.html")
        if User.query.filter_by(username=username).first():
            flash("El nombre de usuario ya existe.", "danger")
            return render_template("auth/register.html")
        if User.query.filter_by(email=email).first():
            flash("El correo electrónico ya está registrado.", "danger")
            return render_template("auth/register.html")

        applicant_role = Role.query.filter_by(name="applicant").first()
        if not applicant_role:
            flash("No se encontró el rol 'applicant'. Contacta al administrador.", "danger")
            return render_template("auth/register.html")


        new_user = User(
            first_name,
            last_name,
            mother_last_name,
            username,
            password, 
            email,
            is_internal,
            applicant_role.id,
            avatar="default.jpg"
        )
        db.session.add(new_user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Error al registrar el usuario.", "danger")
            return render_template("auth/register.html")

        flash("Registro exitoso. Ahora inicia sesión.", "success")
        return redirect(url_for("pages_auth.login_page"))

    return render_template("auth/register.html")

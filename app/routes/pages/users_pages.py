# app/routes/pages/users_pages.py
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Program
from app.services.admission_service import get_admission_state

pages_user = Blueprint("pages_user", __name__, url_prefix="/user")

@pages_user.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    return render_template("user/dashboard.html")

@pages_user.route("/profile", methods=["GET"])
@login_required
def profile():
    # ── Datos base para el panel de progreso ─────────────
    up = current_user.user_program[0] if current_user.user_program else None
    program = up.program if up else None

    if program:
        adm_state = get_admission_state(current_user.id, program.id, up)
    else:
        adm_state = {
            "progress_segments": [],
            "status_count": {},
            "progress_pct": 0,
            "pending_items": [],
            "timeline": []
        }

    context = {"program": program, **adm_state}
    return render_template("user/profile/profile.html", **context)

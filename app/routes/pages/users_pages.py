# app/routes/pages/users_pages.py
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.services.admission_service import get_admission_state
from app.services.dashboard_service import DashboardService
from app.utils.htmx import is_htmx, render_fragment

pages_user = Blueprint("pages_user", __name__, url_prefix="/user")


@pages_user.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    context = DashboardService.build_dashboard_context(
        current_user,
        program_id_param=request.args.get('program_id'),
    )
    context["dashboard_kind"] = DashboardService.dashboard_kind(current_user)
    # Realtime refresh (hx-get on #dashboard-content): the body only, never the shell.
    if is_htmx():
        return render_fragment("user/dashboard/_partials/_dashboard_refresh.html", **context)
    return render_fragment("user/dashboard/dashboard.html", **context)


@pages_user.route("/dashboard/events-widget", methods=["GET"])
@login_required
def events_widget():
    """Fragmento HTML: cuerpo del widget de eventos (tras responder una invitación)."""
    return render_fragment(
        "partials/_events_widget_body.html",
        events_widget=DashboardService.events_widget_for(current_user),
    )


@pages_user.route("/profile/summary", methods=["GET"])
@login_required
def profile_summary():
    """Fragmento HTML: columna de datos de la cabecera del perfil + tarjeta de información personal."""
    return render_fragment("user/profile/_profile_summary_refresh.html")


@pages_user.route("/profile", methods=["GET"])
@login_required
def profile():
    up = current_user.current_user_program()
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

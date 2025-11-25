# app/routes/pages/admin/admin_pages.py
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.routes.pages.admin.review_pages import pages_review
from app.routes.pages.admin.setting_pages import pages_settings
from app.routes.pages.admin.events_pages import pages_events
from app.routes.pages.admin.email_pages import pages_emails

pages_admin = Blueprint("pages_admin", __name__, url_prefix="/admin")

@pages_admin.route("/")
@login_required
@roles_required('postgraduate_admin', 'program_admin', 'social_service')
def home():
    """Página principal del panel de administración"""
    # Para program_admin, obtener su programa coordinado
    program = None
    if current_user.has_role('program_admin') and current_user.coordinated_programs:
        program = current_user.coordinated_programs[0]
    
    # Aquí podrías agregar métricas y datos según el rol
    context = {
        'program': program
    }
    
    return render_template("admin/home.html", **context)

# Monta el sub-blueprint de review
pages_admin.register_blueprint(pages_review)
pages_admin.register_blueprint(pages_settings)
pages_admin.register_blueprint(pages_events)
pages_admin.register_blueprint(pages_emails)

# app/routes/pages/admin/admin_pages.py
from flask import Blueprint
from flask_login import login_required
from app.utils.auth import roles_required
from app.routes.pages.admin.review_pages import pages_review
from app.routes.pages.admin.setting_pages import pages_settings

pages_admin = Blueprint("pages_admin", __name__, url_prefix="/admin")

# Si quieres una portada para /admin en el futuro, podrías agregar:
# @pages_admin.route("/")
# @login_required
# @roles_required('postgraduate_admin', 'program_admin', 'social_service')
# def home():
#     return render_template("admin/home.html")

# Monta el sub-blueprint de review
pages_admin.register_blueprint(pages_review)
pages_admin.register_blueprint(pages_settings)

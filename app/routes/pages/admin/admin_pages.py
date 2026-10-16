# app/routes/pages/admin/admin_pages.py
from flask import Blueprint, redirect, url_for
from flask_login import login_required
from app.utils.permissions import permission_required
from app.routes.pages.admin.review_pages import pages_review
from app.routes.pages.admin.setting_pages import pages_settings
from app.routes.pages.admin.events_pages import pages_events
from app.routes.pages.admin.email_pages import pages_emails

pages_admin = Blueprint("pages_admin", __name__, url_prefix="/admin")

@pages_admin.route("/")
@login_required
@permission_required('admin_review.page.view')
def home():
    """
    /admin/ has no page of its own: it used to render admin/home.html, a
    template that does not exist (500 for every reviewer who typed the URL).
    The review queue is the landing that this same permission grants.
    """
    return redirect(url_for("pages_admin.pages_review.submissions"))

# Monta el sub-blueprint de review
pages_admin.register_blueprint(pages_review)
pages_admin.register_blueprint(pages_settings)
pages_admin.register_blueprint(pages_events)
pages_admin.register_blueprint(pages_emails)

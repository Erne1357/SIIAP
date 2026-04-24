# app/routes/pages/admin/events_pages.py
from flask import Blueprint, render_template
from flask_login import login_required
from app.utils.permissions import permission_required

pages_events = Blueprint(
    'pages_events',
    __name__,
    url_prefix='/events'
)

@pages_events.route('/')
@login_required
@permission_required('events.page.view')
def index():
    """Vista principal de gestión de eventos"""
    return render_template('admin/events/index.html')
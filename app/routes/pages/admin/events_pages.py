# app/routes/pages/admin/events_pages.py
from flask import Blueprint, render_template
from flask_login import login_required
from app.utils.auth import roles_required

pages_events = Blueprint(
    'pages_events',
    __name__,
    url_prefix='/events'
)

@pages_events.route('/')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def index():
    """Vista principal de gestión de eventos"""
    return render_template('admin/events/index.html')
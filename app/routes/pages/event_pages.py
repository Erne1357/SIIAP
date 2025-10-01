# app/routes/pages/events_pages.py
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.event import Event
from app import db

pages_events_public = Blueprint(
    'pages_events_public',
    __name__,
    url_prefix='/events'
)

@pages_events_public.route('/')
@login_required
def list_events():
    """Lista de eventos disponibles para estudiantes"""
    return render_template('events/list.html')

@pages_events_public.route('/<int:event_id>')
@login_required
def view_event(event_id: int):
    """Ver detalles de un evento"""
    event = db.session.get(Event, event_id)
    if not event:
        return render_template('404.html'), 404
    
    return render_template('events/view.html', event=event)
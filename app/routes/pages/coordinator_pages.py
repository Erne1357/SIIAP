# app/routes/pages/coordinator_pages.py
from flask import Blueprint, render_template, current_app
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.models.program import Program
import logging

pages_coordinator = Blueprint('pages_coordinator', __name__, url_prefix='/coordinator')

@pages_coordinator.route('/dashboard')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def dashboard():
    """Dashboard principal del coordinador"""
    # Obtener programas que puede gestionar
    if current_user.role.name == 'program_admin':
        coordinator_programs = Program.query.filter_by(coordinator_id=current_user.id).all()
        current_app.logger.warning(f"Coordinator {current_user.id} manages programs: {[p.id for p in coordinator_programs]}")
    else:
        # Admin puede ver todos
        current_app.logger.warning(f"Admin {current_user.id} accessing all programs")
        coordinator_programs = Program.query.all()
    
    return render_template('coordinator/dashboard.html', 
                         coordinator_programs=coordinator_programs)
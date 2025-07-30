from flask import Blueprint, render_template, request, redirect,flash,url_for
from flask_login import login_required, current_user
from app.services.adminission import get_admission_state
from app import db


user = Blueprint('user', __name__)

@user.route('/dashboard')
@login_required
def dashboard():
    return render_template('user/dashboard.html')


@user.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # 1) Obtén los valores del form
        first = request.form.get('first_name', '').strip()
        last  = request.form.get('last_name', '').strip()
        mother = request.form.get('mother_last_name', '').strip()

        # 2) Validaciones sencillas (opcional)
        if not first or not last:
            flash('Nombre y Apellido Paterno son obligatorios.', 'danger')
            return redirect(url_for('user.profile'))

        # 3) Actualiza el modelo y guarda
        current_user.first_name       = first
        current_user.last_name        = last
        current_user.mother_last_name = mother or None
        db.session.commit()

        flash('Perfil actualizado correctamente.', 'success')
        return redirect(url_for('user.profile'))

    # ── 1. Datos base ──────────────────────────────────────────────
    up = current_user.user_program[0] if current_user.user_program else None  
    program = up.program if up else None

    if program:
        adm_state = get_admission_state(current_user.id, program.id, up)
    else :
        adm_state = {
            "progress_segments": [],
            "status_count": {},
            "progress_pct": 0,
            "pending_items": [],
            "timeline": []
        }
        
    # Contexto para la plantilla
    context = {
        "program": program,
        **adm_state
    }

    return render_template('user/profile/profile.html', **context)

from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services import programs_service as svc

pages_settings = Blueprint('pages_settings', __name__, url_prefix='/settings')

@pages_settings.route('/', methods=['GET'])
@login_required
@roles_required('postgraduate_admin','program_admin')
def index():
    return render_template('admin/settings/archives.html')

@pages_settings.route('/retention', methods=['GET'])
@login_required
@roles_required('postgraduate_admin','program_admin')
def retention():
    return render_template('admin/settings/retention.html')

@pages_settings.route('/users', methods=['GET'])
@login_required
@roles_required('postgraduate_admin','program_admin')
def users():
    return render_template('admin/settings/users.html')

@pages_settings.route('/mails', methods=['GET'])
@login_required
@roles_required('postgraduate_admin','program_admin')
def mails():
    return render_template('admin/settings/mails.html')

@pages_settings.route('/program/<string:slug>', methods=['GET'])
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def config_program(slug):
    """
    Configuración del programa.
    - postgraduate_admin: puede editar todos los programas
    - program_admin: solo puede editar los programas que coordina
    """
    try:
        program = svc.get_program_by_slug(slug)
    except Exception:
        return render_template('404.html'), 404

    # Verificar permisos
    if current_user.role.name == 'program_admin':
        # Verificar que sea coordinador del programa
        if program.coordinator_id != current_user.id:
            abort(403)  # Forbidden

    # postgraduate_admin puede editar cualquier programa
    return render_template('admin/settings/program_config.html', program=program)


@pages_settings.route('/academic-periods', methods=['GET'])
@login_required
@roles_required('postgraduate_admin')
def academic_periods():
    """Gestión de periodos académicos."""
    return render_template('admin/settings/academic_periods.html')
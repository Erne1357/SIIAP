from flask import Blueprint, render_template
from flask_login import login_required
from app.utils.auth import roles_required

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
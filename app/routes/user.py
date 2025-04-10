from flask import Blueprint, render_template
from flask_login import login_required, current_user

user = Blueprint('user', __name__)

@user.route('/dashboard')
@login_required
def dashboard():
    return render_template('user/dashboard.html')

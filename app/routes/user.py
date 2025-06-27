from flask import Blueprint, render_template, request, redirect
from flask_login import login_required, current_user

user = Blueprint('user', __name__)

@user.route('/dashboard')
@login_required
def dashboard():
    return render_template('user/dashboard.html')


@user.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        #Aquí irá la lógia para actualizar el perfil del usuario
        print(request.form)
    else :
        return render_template('user/profile/profile.html')
    


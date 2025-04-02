from flask import Blueprint, render_template, request, redirect, url_for, flash

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Obtener datos del formulario
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Aquí se debe agregar la lógica real de autenticación, por ejemplo consultando la base de datos.
        # Para este ejemplo, se simula que si ambos campos son "admin", el login es exitoso.
        if username == "admin" and password == "admin":
            flash("Inicio de sesión exitoso", "success")
            return redirect(url_for('user.dashboard'))
        else:
            flash("Credenciales incorrectas", "danger")
            return render_template('auth/login.html')
    
    return render_template('auth/login.html')

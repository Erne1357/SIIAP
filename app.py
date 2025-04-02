from flask import Flask, render_template, redirect
from app.config import Config

def create_app():
    # Create the Flask application
    app = Flask(__name__,template_folder='app/templates', static_folder='app/static')
    app.config.from_object(Config)
    
    # Define a basic route for login
    @app.route('/')
    def redirect_to_login():
        return redirect("/login", code=302)

    @app.route('/login')
    def login():
        return render_template('auth/login.html')
    
    return app

app = create_app()

if __name__ == '__main__':
    # Run the app on host 0.0.0.0 so it's accessible from Docker
    app.run(host='0.0.0.0', debug=True)

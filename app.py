from flask import Flask, render_template
from app.config import Config

def create_app():
    # Create the Flask application
    app = Flask(__name__,template_folder='app/templates', static_folder='app/static')
    app.config.from_object(Config)
    
    # Define a basic route for login
    @app.route('/login')
    def login():
        return render_template('auth/login.html')
    
    return app

if __name__ == '__main__':
    app = create_app()
    # Run the app on host 0.0.0.0 so it's accessible from Docker
    app.run(host='0.0.0.0', debug=True)

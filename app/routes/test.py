from flask import Blueprint, jsonify
from app import db
from app.models.role import Role
from app.models.user import User
from datetime import datetime
from werkzeug.security import generate_password_hash

test_bp = Blueprint('test', __name__)

@test_bp.route('/test_db')
def test_db():
    # Verifica si el rol "user" existe, de lo contrario se crea
    role = Role.query.filter_by(name='user').first()
    if not role:
        role = Role(name='user', description='test')
        db.session.add(role)
        db.session.commit()
    
    # Inserta un usuario de prueba con el rol "user"
    new_user = User(
        first_name='Juan',
        last_name='Pérez',
        mother_last_name='González',
        username='juanp',
        password='123456',
        email='juan@example.com',
        role_id=role.id
    )
    db.session.add(new_user)
    db.session.commit()
    
    # Realiza una consulta para obtener todos los usuarios
    users = User.query.all()
    users_data = [
        {
            'id': u.id,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'mother_last_name': u.mother_last_name,
            'username': u.username,
            'email': u.email,
            'registration_date': u.registration_date.isoformat(),
            'is_internal': u.is_internal,
            'role': u.role.name  # Utilizando la relación
        }
        for u in users
    ]
    
    return jsonify(users_data)

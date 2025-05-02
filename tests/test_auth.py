# tests/test_auth.py

import unittest
from datetime import datetime, timezone, timedelta
from app import create_app, db
from app.models.user import User
from app.models.role import Role
from werkzeug.security import generate_password_hash

class AuthTestCase(unittest.TestCase):
    def setUp(self):
        test_config = {
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'SECRET_KEY': 'test-secret-key'
        }
        self.app = create_app(test_config)
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            # Insertar un rol de prueba (por ejemplo, 'admin')
            role = Role(name='admin', description='Administrador de prueba')
            db.session.add(role)
            db.session.commit()
            
            # Insertar un usuario de prueba con username 'admin' y password 'admin'
            test_user = User(
                first_name='Admin',
                last_name='User',
                mother_last_name='Test',
                username='admin',
                password='admin',  # El constructor realizará el hash
                email='admin@test.com',
                role_id=role.id
            )
            db.session.add(test_user)
            db.session.commit()
    
    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_successful_login(self):
        # Probar login con credenciales correctas
        response = self.client.post('/login', data={
            'username': 'admin',
            'password': 'admin'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Verificar que se redirige al dashboard
        self.assertIn(b'Dashboard', response.data)
    
    def test_invalid_login(self):
        # Probar login con contraseña incorrecta
        response = self.client.post('/login', data={
            'username': 'admin',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Se espera que se muestre mensaje de error (usando flash)
        self.assertIn(b'Credenciales incorrectas', response.data)
    
    def test_logout(self):
        # Inicia sesión y luego cierra sesión
        self.client.post('/login', data={
            'username': 'admin',
            'password': 'admin'
        }, follow_redirects=True)
        response = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Has cerrado sesi', response.data)  # Verifica parte del mensaje de logout
    
    def test_session_timeout(self):
        # Inicia sesión
        self.client.post('/login', data={
            'username': 'admin',
            'password': 'admin'
        }, follow_redirects=True)
        # Modificar manualmente la marca de tiempo de la sesión para simular inactividad
        with self.client.session_transaction() as sess:
            # Simula que la última actividad fue hace 16 minutos (más de los 15 permitidos)
            sess['last_activity'] = (datetime.now(timezone.utc) - timedelta(minutes=16)).timestamp()
        # Hacer una petición para que se active el before_request y se verifique la expiración
        response = self.client.get('/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Se espera ver un mensaje de sesión expirada
        self.assertIn(b'Tu sesi', response.data)
    
    def test_keepalive(self):
        # Inicia sesión
        self.client.post('/login', data={
            'username': 'admin',
            'password': 'admin'
        }, follow_redirects=True)
        # Llama a la ruta de keepalive
        response = self.client.get('/keepalive')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'OK')

if __name__ == '__main__':
    unittest.main()

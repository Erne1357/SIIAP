from app import db
from flask import url_for
from flask_login import UserMixin
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    mother_last_name = db.Column(db.String(50))
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Aseguramos la longitud para el hash
    email = db.Column(db.String(100), unique=True, nullable=False)
    last_login = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)
    is_internal = db.Column(db.Boolean, default=False)
    scolarship_type = db.Column(db.String(50), nullable=True)
    registration_date = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    avatar = db.Column(db.String(255), default='default.jpg', nullable=True)
    must_change_password = db.Column(db.Boolean, default=True, nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    control_number = db.Column(db.String(20), unique=True, nullable=True)
    control_number_assigned_at = db.Column(db.DateTime, nullable=True)

    role = db.relationship('Role', back_populates='users', uselist=False)
    user_program = db.relationship('UserProgram', back_populates='user')
    submissions = db.relationship(
        'Submission',
        foreign_keys='Submission.user_id',
        back_populates='user',
        cascade='all, delete-orphan'
    )
    reviews = db.relationship(
        'Submission',
        foreign_keys='Submission.reviewer_id',
        back_populates='reviewer'
    )

    phone = db.Column(db.String(20))
    mobile_phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    curp = db.Column(db.String(18))
    rfc = db.Column(db.String(13))
    birth_date = db.Column(db.Date)
    birth_place = db.Column(db.String(200))
    cedula_profesional = db.Column(db.String(20))
    nss = db.Column(db.String(15))

    # Contacto de emergencia
    emergency_contact_name = db.Column(db.String(200))
    emergency_contact_phone = db.Column(db.String(20))
    emergency_contact_relationship = db.Column(db.String(50))

    # Campo para marcar perfil completo (calculado automáticamente)
    profile_completed = db.Column(db.Boolean, default=False, nullable=False)


    def __init__(self, first_name, last_name, mother_last_name, username, password, email, is_internal, role_id, avatar):
        self.first_name = first_name
        self.last_name = last_name
        self.mother_last_name = mother_last_name
        self.username = username
        self.password = generate_password_hash(password)
        self.email = email
        self.registration_date = datetime.now(timezone.utc)
        self.last_login = datetime.now(timezone.utc)
        self.is_internal = is_internal
        self.role_id = role_id
        self.avatar = avatar
        self.must_change_password = True
    
    def is_profile_complete(self):
        """
        Verifica si el perfil está completo basándose en los campos requeridos.
        Los campos básicos (nombre, email, etc.) ya están en el registro.
        Los campos adicionales son los que determinan si está "completo".
        """
        required_fields = [
            self.phone or self.mobile_phone,  # Al menos uno de los teléfonos
            self.address,
            self.curp,
            self.birth_date,
            self.emergency_contact_name,
            self.emergency_contact_phone,
            self.emergency_contact_relationship
        ]
        
        # Todos los campos requeridos deben tener valor
        return all(field and str(field).strip() if isinstance(field, str) else field for field in required_fields)

    def update_profile_completion_status(self):
        """
        Actualiza automáticamente el estado de profile_completed
        """
        self.profile_completed = self.is_profile_complete()
        return self.profile_completed

    @property
    def avatar_url(self):
        if self.avatar and self.avatar != 'default.jpg':
            return url_for('api_files.avatar', user_id=self.id, filename=self.avatar)
        return url_for('static', filename='assets/images/default.jpg')
    
    def has_role(self, *role_names):
        """
        Comprueba si el usuario tiene **todos** los roles pasados.
        Si sólo hay uno, verifica su existencia en self.roles.
        """
        if not self.role:
            return False
        return self.role.name in role_names
    
    def deactivate(self):
        """Desactiva el usuario"""
        self.is_active = False
        
    def activate(self):
        """Activa el usuario"""
        self.is_active = True

    def assign_control_number(self, control_number):
        """
        Asigna un número de control al usuario y actualiza su username.
        
        Args:
            control_number (str): El número de control (ej: M21111182)
        """
        self.control_number = control_number
        self.username = control_number
        self.control_number_assigned_at = datetime.now(timezone.utc)

    def can_be_deleted(self):
        """
        Verifica si el usuario puede ser eliminado.
        Un usuario puede ser eliminado si no tiene:
        - Documentos subidos (submissions)
        - Citas programadas (appointments)
        """
        has_submissions = len(self.submissions) > 0 if hasattr(self, 'submissions') else False
        # has_appointments = len(self.appointments) > 0 if hasattr(self, 'appointments') else False
        
        return not has_submissions  # and not has_appointments

    def to_dict(self, include_sensitive=False):
        user_data = {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'mother_last_name': self.mother_last_name,
            'username': self.username,
            'email': self.email,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_internal': self.is_internal,
            'scolarship_type': self.scolarship_type,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None,
            'role': self.role.name if self.role else None,
            'avatar_url': self.avatar_url,
            'must_change_password': self.must_change_password,
            'profile_completed': self.profile_completed
        }
        if include_sensitive:
            user_data.update({
                'is_active': self.is_active,
                'control_number': self.control_number,
                'control_number_assigned_at': self.control_number_assigned_at.isoformat() if self.control_number_assigned_at else None
            })

        return user_data
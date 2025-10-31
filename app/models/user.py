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
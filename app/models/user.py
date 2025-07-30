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
    scolarship_type = db.Column(db.String(50))
    registration_date = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    avatar = db.Column(db.String(255), default='default.jpg', nullable = True)

    role = db.relationship('Role', back_populates='users',uselist=False)
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

    def __init__(self, first_name, last_name, mother_last_name, username, password, email,is_internal,scolarship_type, role_id, avatar):
        self.first_name = first_name
        self.last_name = last_name
        self.mother_last_name = mother_last_name
        self.username = username
        self.password = generate_password_hash(password)
        self.email = email
        self.registration_date = datetime.now(timezone.utc)
        self.last_login = datetime.now(timezone.utc)
        self.is_internal = is_internal
        self.scolarship_type = scolarship_type
        self.role_id = role_id
        self.avatar = avatar
    
    @property
    def avatar_url(self):
        if self.avatar and self.avatar != 'default.jpg':
            return url_for('files.avatar', user_id=self.id, filename=self.avatar)
        return url_for('static', filename='assets/images/default.jpg')
    
    def has_role(self, *role_names):
        """
        Comprueba si el usuario tiene **todos** los roles pasados.
        Si sólo hay uno, verifica su existencia en self.roles.
        """
        if not self.role:
            return False
        return self.role.name in role_names

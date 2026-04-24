from app import db
from flask import url_for, g
from flask_login import UserMixin
from datetime import datetime, timezone
from app.utils.datetime_utils import now_local
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
    last_login = db.Column(db.DateTime, default=now_local, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)
    scolarship_type = db.Column(db.String(50), nullable=True)
    registration_date = db.Column(db.DateTime, default=now_local, nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    avatar = db.Column(db.String(255), default='default.jpg', nullable=True)
    must_change_password = db.Column(db.Boolean, default=True, nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    control_number = db.Column(db.String(20), unique=True, nullable=True)
    control_number_assigned_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local, nullable=False)

    role = db.relationship('Role', back_populates='users', uselist=False)
    user_program = db.relationship(
        'UserProgram',
        foreign_keys='UserProgram.user_id',
        back_populates='user'
    )

    coordinated_programs = db.relationship('Program', back_populates='coordinator')

    # Permisos directos asignados al usuario (delegación / casos especiales)
    direct_permissions = db.relationship(
        'UserPermission',
        foreign_keys='UserPermission.user_id',
        back_populates='user',
        cascade='all, delete-orphan'
    )
    
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
    histories = db.relationship(
        'UserHistory', 
        foreign_keys='UserHistory.user_id',
        back_populates='user', 
        cascade='all, delete-orphan'
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


    def __init__(self, first_name, last_name, mother_last_name, username, password, email, is_internal, role_id, avatar='default.jpg', must_change_password=True):
        self.first_name = first_name
        self.last_name = last_name
        self.mother_last_name = mother_last_name
        self.username = username
        self.password = generate_password_hash(password)
        self.email = email
        self.registration_date = now_local()
        self.last_login = now_local()
        self.is_internal = is_internal
        self.role_id = role_id
        self.avatar = avatar
        self.must_change_password = must_change_password
    
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
    
    def has_permission(self, codename, program_id=None):
        """
        Evalúa si el usuario tiene el permiso indicado.

        Orden de evaluación:
          1. Permisos base del rol (RolePermission, del seed)
          2. Overrides activos del rol (RolePermissionOverride)
          3. Permisos directos activos y no vencidos (UserPermission)

        Caché por request (flask.g) para evitar N+1 queries.
        Si program_id se especifica, los UserPermission deben tener
        ese program_id o NULL (global).
        """
        cache_key = f'_perm_cache_{self.id}_{program_id}'
        if not hasattr(g, cache_key):
            from app.models.role_permission import RolePermission, RolePermissionOverride
            from app.models.user_permission import UserPermission
            from app.utils.datetime_utils import now_local

            codenames = set()

            # 1. Permisos base del rol
            if self.role_id:
                base = (
                    db.session.query(RolePermission)
                    .join(RolePermission.permission)
                    .filter(RolePermission.role_id == self.role_id)
                    .all()
                )
                codenames.update(rp.permission.codename for rp in base)

            # 2. Overrides activos del rol
            if self.role_id:
                overrides = (
                    db.session.query(RolePermissionOverride)
                    .join(RolePermissionOverride.permission)
                    .filter(
                        RolePermissionOverride.role_id == self.role_id,
                        RolePermissionOverride.is_active == True
                    )
                    .all()
                )
                codenames.update(ov.permission.codename for ov in overrides)

            # 3. Permisos directos del usuario (activos y no vencidos)
            now = now_local()
            direct_q = (
                db.session.query(UserPermission)
                .join(UserPermission.permission)
                .filter(
                    UserPermission.user_id == self.id,
                    UserPermission.is_active == True,
                    db.or_(
                        UserPermission.expires_at == None,
                        UserPermission.expires_at > now
                    ),
                )
            )
            if program_id is not None:
                direct_q = direct_q.filter(
                    db.or_(
                        UserPermission.program_id == None,
                        UserPermission.program_id == program_id
                    )
                )
            codenames.update(up.permission.codename for up in direct_q.all())

            setattr(g, cache_key, codenames)

        return codename in getattr(g, cache_key)
    
    def get_accessible_program_ids(self):
        """
        Retorna el conjunto de program_ids sobre los que este usuario puede operar.

        Reglas:
          - Si el usuario tiene 'academic_periods.api.create' (jefe de posgrado):
            retorna None → puede operar sobre cualquier programa.
          - Si es coordinador: incluye sus programas coordinados.
          - Si tiene UserPermission delegado con program_id: incluye ese programa.
          - La unión de ambas fuentes es el conjunto accesible.

        Returns:
          set[int] | None  — None significa "todos los programas" (acceso global).
        """
        if self.has_permission('academic_periods.api.create'):
            return None

        pids = set()
        for p in self.coordinated_programs:
            pids.add(p.id)

        from app.models.user_permission import UserPermission
        from app.utils.datetime_utils import now_local
        now = now_local()
        delegated = (
            db.session.query(UserPermission)
            .filter(
                UserPermission.user_id == self.id,
                UserPermission.is_active == True,
                UserPermission.program_id.isnot(None),
                db.or_(
                    UserPermission.expires_at == None,
                    UserPermission.expires_at > now
                ),
            )
            .all()
        )
        for up in delegated:
            pids.add(up.program_id)

        return pids

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
        self.control_number_assigned_at = now_local()

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
                'control_number_assigned_at': self.control_number_assigned_at.isoformat() if self.control_number_assigned_at else None,
                'program' : {
                    'id': self.user_program[0].program.id,
                    'name': self.user_program[0].program.name,
                    'slug': self.user_program[0].program.slug
                } if self.user_program else None,
                'histories': [h.to_dict() for h in (self.histories or [])]
            })

        return user_data
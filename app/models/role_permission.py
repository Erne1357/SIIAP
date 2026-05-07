from app import db
from app.utils.datetime_utils import now_local


class RolePermission(db.Model):
    """Permisos base de cada rol, definidos por seed. No se modifican desde UI."""
    __tablename__ = 'role_permission'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
    )

    # Relationships
    role = db.relationship('Role', back_populates='role_permissions')
    permission = db.relationship('Permission', back_populates='role_permissions')

    def __init__(self, role_id, permission_id):
        self.role_id = role_id
        self.permission_id = permission_id

    def __repr__(self):
        return f'<RolePermission role={self.role_id} perm={self.permission_id}>'


class RolePermissionOverride(db.Model):
    """
    Permisos adicionales que el jefe de posgrado agrega a un rol desde la UI.
    Solo se pueden AGREGAR permisos (granted=True). No se pueden quitar los del seed.
    Cuando se revierte un override, is_active pasa a False (no se borra el registro).
    """
    __tablename__ = 'role_permission_override'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now_local, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    role = db.relationship('Role', back_populates='permission_overrides')
    permission = db.relationship('Permission', back_populates='role_overrides')

    def __init__(self, role_id, permission_id):
        self.role_id = role_id
        self.permission_id = permission_id

    def revoke(self):
        from app.utils.datetime_utils import now_local
        self.is_active = False
        self.revoked_at = now_local()

    def to_dict(self):
        return {
            'id': self.id,
            'role_id': self.role_id,
            'permission_id': self.permission_id,
            'permission_codename': self.permission.codename if self.permission else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
        }

    def __repr__(self):
        return f'<RolePermissionOverride role={self.role_id} perm={self.permission_id} active={self.is_active}>'

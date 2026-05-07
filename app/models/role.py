from app import db

class Role(db.Model):
    __tablename__ = 'role'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    
    # Relación: Un rol tiene muchos usuarios
    users = db.relationship('User', back_populates='role')

    # Permisos base del rol (definidos por seed)
    role_permissions = db.relationship(
        'RolePermission',
        back_populates='role',
        cascade='all, delete-orphan'
    )

    # Overrides de permisos agregados desde la UI por el jefe de posgrado
    permission_overrides = db.relationship(
        'RolePermissionOverride',
        back_populates='role',
        cascade='all, delete-orphan'
    )

    def __init__(self, name, description):
        self.name = name
        self.description = description
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }

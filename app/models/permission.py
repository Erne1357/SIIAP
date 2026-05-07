from app import db
from app.utils.datetime_utils import now_local


class Permission(db.Model):
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    codename = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    resource = db.Column(db.String(60), nullable=False)
    perm_type = db.Column(db.String(10), nullable=False)   # 'api' | 'page'
    action = db.Column(db.String(60), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now_local, nullable=False)

    # Relationships
    role_permissions = db.relationship(
        'RolePermission',
        back_populates='permission',
        cascade='all, delete-orphan'
    )
    role_overrides = db.relationship(
        'RolePermissionOverride',
        back_populates='permission',
        cascade='all, delete-orphan'
    )
    user_permissions = db.relationship(
        'UserPermission',
        back_populates='permission',
        cascade='all, delete-orphan'
    )
    audit_entries = db.relationship(
        'RolePermissionAudit',
        back_populates='permission',
        cascade='all, delete-orphan'
    )

    def __init__(self, codename, display_name, resource, perm_type, action, description=None):
        self.codename = codename
        self.display_name = display_name
        self.resource = resource
        self.perm_type = perm_type
        self.action = action
        self.description = description

    def to_dict(self):
        return {
            'id': self.id,
            'codename': self.codename,
            'display_name': self.display_name,
            'description': self.description,
            'resource': self.resource,
            'perm_type': self.perm_type,
            'action': self.action,
            'is_active': self.is_active,
        }

    def __repr__(self):
        return f'<Permission {self.codename}>'

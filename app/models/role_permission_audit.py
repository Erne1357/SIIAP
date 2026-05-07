from app import db
from app.utils.datetime_utils import now_local


class RolePermissionAudit(db.Model):
    """
    Registro de auditoría de todos los cambios realizados a RolePermissionOverride.
    Guarda quién hizo el cambio, cuándo, qué acción y el estado previo.
    """
    __tablename__ = 'role_permission_audit'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), nullable=False)

    # 'grant' = se agregó el override | 'revert' = se revirtió el override
    action = db.Column(db.String(20), nullable=False)

    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    performed_at = db.Column(db.DateTime, default=now_local, nullable=False)
    reason = db.Column(db.Text, nullable=True)

    # Snapshot JSON del estado del override antes del cambio (para poder auditar)
    previous_state = db.Column(db.JSON, nullable=True)

    # Relationships
    role = db.relationship('Role', foreign_keys=[role_id])
    permission = db.relationship('Permission', back_populates='audit_entries')
    performed_by_user = db.relationship('User', foreign_keys=[performed_by])

    def __init__(self, role_id, permission_id, action, performed_by, reason=None, previous_state=None):
        self.role_id = role_id
        self.permission_id = permission_id
        self.action = action
        self.performed_by = performed_by
        self.reason = reason
        self.previous_state = previous_state

    def to_dict(self):
        return {
            'id': self.id,
            'role_id': self.role_id,
            'role_name': self.role.name if self.role else None,
            'permission_id': self.permission_id,
            'permission_codename': self.permission.codename if self.permission else None,
            'action': self.action,
            'performed_by': self.performed_by,
            'performed_by_name': (
                f'{self.performed_by_user.first_name} {self.performed_by_user.last_name}'
                if self.performed_by_user else None
            ),
            'performed_at': self.performed_at.isoformat() if self.performed_at else None,
            'reason': self.reason,
            'previous_state': self.previous_state,
        }

    def __repr__(self):
        return f'<RolePermissionAudit role={self.role_id} perm={self.permission_id} action={self.action}>'

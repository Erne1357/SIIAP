# app/models/user_history.py
from app import db
from datetime import datetime, timezone

class UserHistory(db.Model):
    """
    Registra todas las acciones administrativas realizadas sobre un usuario.
    """
    __tablename__ = 'user_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relaciones
    user = db.relationship('User', foreign_keys=[user_id], backref='history_entries')
    admin = db.relationship('User', foreign_keys=[admin_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'admin_id': self.admin_id,
            'admin_name': f"{self.admin.first_name} {self.admin.last_name}" if self.admin else "Sistema",
            'action': self.action,
            'action_label': self.get_action_label(),
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }
    
    def get_action_label(self):
        """Retorna etiqueta legible del tipo de acción"""
        labels = {
            'password_reset': 'Contraseña restablecida',
            'password_changed': 'Contraseña cambiada',
            'deactivated': 'Usuario desactivado',
            'activated': 'Usuario activado',
            'control_number_assigned': 'Número de control asignado',
            'role_changed': 'Rol modificado',
            'profile_updated': 'Perfil actualizado',
            'deleted': 'Usuario eliminado',
            'created': 'Usuario creado',
            'basic_info_updated': 'Información básica actualizada',
            'profile_completed': 'Perfil completado'
        }
        return labels.get(self.action, self.action)
"""
Modelo para el historial persistente de ejecuciones de tareas Celery.

Cada vez que una tarea se inicia, completa, falla o reintenta,
se registra un TaskLog en PostgreSQL para consulta desde el panel admin.
"""

from datetime import datetime
from app import db


# Nombres legibles para las tareas conocidas del sistema
TASK_DISPLAY_NAMES = {
    'app.tasks.maintenance.cleanup_expired_admission_files': 'Limpieza de archivos expirados',
    'app.tasks.maintenance.apply_retention_policies':        'Aplicar políticas de retención',
    'app.tasks.maintenance.cleanup_old_notifications':       'Limpiar notificaciones antiguas',
    'app.tasks.notifications.send_bulk_notification':        'Envío masivo de notificaciones',
    'app.tasks.notifications.send_bulk_notification_by_filter': 'Envío masivo por filtro',
}


class TaskLog(db.Model):
    __tablename__ = 'task_logs'

    id            = db.Column(db.Integer, primary_key=True)
    task_id       = db.Column(db.String(255), unique=True, nullable=False, index=True)
    task_name     = db.Column(db.String(255), nullable=False, index=True)

    # 'pending' | 'started' | 'success' | 'failure' | 'retry' | 'revoked'
    status        = db.Column(db.String(20), nullable=False, default='pending', index=True)

    # 'manual' | 'scheduled'
    triggered_by  = db.Column(db.String(20), nullable=False, default='scheduled')

    # Si fue ejecutado manualmente, qué usuario lo disparó
    triggered_by_user_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=True
    )

    started_at    = db.Column(db.DateTime, nullable=True)
    finished_at   = db.Column(db.DateTime, nullable=True)

    # Argumentos con los que se invocó
    kwargs        = db.Column(db.JSON, nullable=True)

    # Resultado devuelto por la tarea (JSON)
    result        = db.Column(db.JSON, nullable=True)

    # Mensaje de error en caso de fallo o reintento
    error_message = db.Column(db.Text, nullable=True)

    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relación con usuario (opcional)
    triggered_user = db.relationship(
        'User', foreign_keys=[triggered_by_user_id], lazy='select'
    )

    # ─── Propiedades calculadas ────────────────────────────────────────────────

    @property
    def display_name(self):
        return TASK_DISPLAY_NAMES.get(self.task_name, self.task_name)

    @property
    def duration_seconds(self):
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at).total_seconds(), 2)
        return None

    # ─── Serialización ────────────────────────────────────────────────────────

    def to_dict(self):
        triggered_user_name = None
        if self.triggered_user:
            triggered_user_name = (
                f"{self.triggered_user.first_name} {self.triggered_user.last_name}"
            ).strip() or self.triggered_user.email

        return {
            'id':                   self.id,
            'task_id':              self.task_id,
            'task_name':            self.task_name,
            'display_name':         self.display_name,
            'status':               self.status,
            'triggered_by':         self.triggered_by,
            'triggered_by_user':    triggered_user_name,
            'started_at':           self.started_at.isoformat()  if self.started_at  else None,
            'finished_at':          self.finished_at.isoformat() if self.finished_at else None,
            'duration_seconds':     self.duration_seconds,
            'kwargs':               self.kwargs,
            'result':               self.result,
            'error_message':        self.error_message,
            'created_at':           self.created_at.isoformat()  if self.created_at  else None,
        }

    def __repr__(self):
        return f'<TaskLog {self.task_name} [{self.status}] {self.task_id[:8]}>'

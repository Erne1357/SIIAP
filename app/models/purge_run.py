# app/models/purge_run.py
"""
Modelo para registrar respaldos ZIP previos a la purga física de archivos.

Flujo:
  pending_download → downloaded → purged
  cualquier estado → cancelled (admin abort) | expired (sweep timeout)

El ZIP se guarda en instance/backups/purge/<run_id>.zip y solo se borra
cuando el run llega a estados terminales (purged | cancelled | expired).
La purga real de archivos físicos solo ocurre en confirm_purge cuando el
run ya está en estado 'downloaded'.
"""

from datetime import timedelta

from app import db
from app.utils.datetime_utils import now_local


PURGE_TYPES = (
    'admission_expired_with_files',
    'admission_delta3_plus',
    'retention_policy',
    'transition_snapshot',
)

PURGE_STATUSES = (
    'pending_download',
    'downloaded',
    'purged',
    'cancelled',
    'expired',
)


def _default_expires_at():
    return now_local() + timedelta(days=7)


class PurgeRun(db.Model):
    __tablename__ = 'purge_run'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    initiated_by = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False
    )
    initiated_at = db.Column(db.DateTime, default=now_local, nullable=False)

    purge_type = db.Column(db.String(40), nullable=False, index=True)
    source_period_id = db.Column(
        db.Integer, db.ForeignKey('academic_period.id'), nullable=True
    )
    target_period_id = db.Column(
        db.Integer, db.ForeignKey('academic_period.id'), nullable=True
    )
    program_id = db.Column(
        db.Integer, db.ForeignKey('program.id'), nullable=True
    )

    target_user_program_ids = db.Column(db.JSON, nullable=False)

    archive_path = db.Column(db.String(500), nullable=True)
    archive_size_bytes = db.Column(db.BigInteger, nullable=True)
    archive_sha256 = db.Column(db.String(64), nullable=True)
    archive_downloaded_at = db.Column(db.DateTime, nullable=True)

    purged_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(
        db.DateTime, nullable=False, default=_default_expires_at
    )

    status = db.Column(
        db.String(20), nullable=False, default='pending_download', index=True
    )
    notes = db.Column(db.Text, nullable=True)

    initiator = db.relationship('User', foreign_keys=[initiated_by])
    source_period = db.relationship(
        'AcademicPeriod', foreign_keys=[source_period_id]
    )
    target_period = db.relationship(
        'AcademicPeriod', foreign_keys=[target_period_id]
    )
    program = db.relationship('Program', foreign_keys=[program_id])

    def is_terminal(self) -> bool:
        return self.status in ('purged', 'cancelled', 'expired')

    def can_download(self) -> bool:
        return self.status in ('pending_download', 'downloaded')

    def can_confirm_purge(self) -> bool:
        # transition_snapshot no purga archivos; queda en 'downloaded' como terminal funcional.
        if self.purge_type == 'transition_snapshot':
            return False
        return self.status == 'downloaded'

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'run_id': self.run_id,
            'initiated_by': self.initiated_by,
            'initiated_at': self.initiated_at.isoformat() if self.initiated_at else None,
            'purge_type': self.purge_type,
            'source_period_id': self.source_period_id,
            'target_period_id': self.target_period_id,
            'program_id': self.program_id,
            'target_user_program_ids': self.target_user_program_ids or [],
            'item_count': len(self.target_user_program_ids or []),
            'archive_size_bytes': self.archive_size_bytes,
            'archive_sha256': self.archive_sha256,
            'archive_downloaded_at': (
                self.archive_downloaded_at.isoformat()
                if self.archive_downloaded_at else None
            ),
            'purged_at': self.purged_at.isoformat() if self.purged_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'status': self.status,
            'notes': self.notes,
        }

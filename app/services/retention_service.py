from datetime import datetime, timedelta
from app import db
from app.models.retention_policy import RetentionPolicy
from app.models.submission import Submission
from app.models.user_program import UserProgram

class RetentionService:
    @staticmethod
    def compute_candidates(now:datetime) -> list[Submission]:
        """
        Retorna submissions candidatas a borrado según retention_policy.
        - apply_after: 'graduated'|'dropped'|'enrollment'
        """
        policies = db.session.query(RetentionPolicy).all()
        candidates = []

        for pol in policies:
            q = db.session.query(Submission).filter(Submission.archive_id == pol.archive_id)

            if pol.keep_forever:
                continue
            if pol.keep_years is None:
                continue

            if pol.apply_after == 'enrollment':
                # comparar contra enrollment_date del user_program (primero por programa del submission)
                # Este cálculo puede variar si tienes múltiples user_program para el user.
                q = q.join(UserProgram, UserProgram.user_id == Submission.user_id)
                threshold = now - timedelta(days=pol.keep_years*365)
                q = q.filter(UserProgram.enrollment_date <= threshold)
            else:
                # En esta versión mínima, filtra por antigüedad general del archivo
                # (el estado final se controla con admission_status).
                threshold = now - timedelta(days=pol.keep_years*365)
                q = q.filter(Submission.upload_date <= threshold)

            candidates.extend(q.all())

        return candidates

    @staticmethod
    def purge_submissions(submission_ids:list[int]) -> int:
        """
        Borra lógicamente los registros; si quieres borrar archivos físicos, hazlo en un job aparte.
        """
        if not submission_ids:
            return 0
        deleted = db.session.query(Submission).filter(Submission.id.in_(submission_ids)).delete(synchronize_session=False)
        db.session.commit()
        return deleted


# --------------------------------------------------------------------------
# Policy CRUD and purge-with-history (used by app/routes/api/retention_api.py)
# --------------------------------------------------------------------------
import logging as _logging

from sqlalchemy import select as _select

from app.models.archive import Archive as _Archive
from app.services.errors import NotFoundError as _NotFoundError
from app.services.public_id_service import uuid_for as _uuid_for
from app.services.user_history_service import UserHistoryService as _UserHistoryService

_log = _logging.getLogger(__name__)


def purge_with_history(raw_submission_uuids, admin_id: int) -> int:
    """Purge submissions given by public UUID and log each purge in the history.

    Unknown UUIDs are ignored. Returns the number of deleted rows.
    """
    submission_ids = [
        row.id for row in (
            Submission.by_uuid(raw) for raw in (raw_submission_uuids or [])
        ) if row is not None
    ]

    # Collect document info before deleting, for the history.
    submissions_info = []
    if submission_ids:
        rows = db.session.execute(
            _select(Submission, _Archive).join(_Archive, Submission.archive_id == _Archive.id)
            .where(Submission.id.in_(submission_ids))
        ).all()
        for submission, archive in rows:
            submissions_info.append({
                'user_id': submission.user_id,
                'archive_name': archive.name,
                # Public handle, not the primary key: this value ends up in
                # `reason`, which the history returns to the student.
                'submission_ref': str(submission.uuid),
            })

    deleted = RetentionService.purge_submissions(submission_ids)

    for info in submissions_info:
        try:
            _UserHistoryService.log_document_purged(
                user_id=info['user_id'],
                archive_name=info['archive_name'],
                reason=f"Eliminación por política de retención (ref: {info['submission_ref']})",
                admin_id=admin_id,
            )
        except Exception as e:
            _log.error(f"Error al registrar eliminación de documento en historial: {e}")

    try:
        db.session.commit()
    except Exception as e:
        _log.error(f"Error al guardar historial de eliminaciones: {e}")

    return deleted


def list_policies() -> list[dict]:
    """All retention policies serialised for the API (archive as public UUID)."""
    rows = db.session.execute(_select(RetentionPolicy)).scalars().all()
    return [{
        # The policy `id` stays an integer (no public handle); `archive_id`
        # names an Archive and goes out as UUID.
        "id": r.id,
        "archive_id": _uuid_for(_Archive, r.archive_id),
        "keep_forever": bool(r.keep_forever),
        "keep_years": r.keep_years,
        "apply_after": r.apply_after,
    } for r in rows]


def upsert_policy(raw_archive_uuid: str, keep_forever: bool, keep_years, apply_after: str) -> tuple[int, bool]:
    """Create or update the single policy of an archive. Returns (id, created).

    Raises NotFoundError("Archivo no existe") for an unknown archive.
    """
    archive = _Archive.by_uuid(raw_archive_uuid)
    if not archive:
        raise _NotFoundError("Archivo no existe")
    existing = db.session.execute(
        _select(RetentionPolicy).where(RetentionPolicy.archive_id == archive.id)
    ).scalar_one_or_none()
    try:
        if existing:
            existing.keep_forever = keep_forever
            existing.keep_years = keep_years
            existing.apply_after = apply_after
            db.session.commit()
            return existing.id, False
        rp = RetentionPolicy(
            archive_id=archive.id,
            keep_forever=keep_forever,
            keep_years=keep_years,
            apply_after=apply_after,
        )
        db.session.add(rp)
        db.session.commit()
        return rp.id, True
    except Exception:
        db.session.rollback()
        raise


def update_policy(policy_id: int, keep_forever: bool, keep_years, apply_after: str) -> int:
    """Update a policy; raises NotFoundError("Política no encontrada")."""
    rp = db.session.get(RetentionPolicy, policy_id)
    if not rp:
        raise _NotFoundError("Política no encontrada")
    try:
        rp.keep_forever = keep_forever
        rp.keep_years = keep_years
        rp.apply_after = apply_after
        db.session.commit()
        return rp.id
    except Exception:
        db.session.rollback()
        raise


def delete_policy(policy_id: int) -> int:
    """Delete a policy; raises NotFoundError("Política no encontrada")."""
    rp = db.session.get(RetentionPolicy, policy_id)
    if not rp:
        raise _NotFoundError("Política no encontrada")
    try:
        db.session.delete(rp)
        db.session.commit()
        return policy_id
    except Exception:
        db.session.rollback()
        raise

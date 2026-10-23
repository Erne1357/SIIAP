"""
Archive service — the document catalog (`Archive` rows) and their templates.

Backs `app/routes/api/archives_api.py`. Framework-agnostic in the project
sense: no `request`, no `g`, no `current_user`; callers pass the scope sets and
the acting user's id explicitly. Filesystem locations come from
`current_app.instance_path` / `ALLOWED_DOC_EXT`, as in the other file services.
"""
from __future__ import annotations

import logging
import os
import shutil
from typing import Optional, Set

from flask import current_app
from sqlalchemy import func, join, select
from werkzeug.utils import secure_filename

from app import db
from app.models.archive import Archive
from app.models.phase import Phase
from app.models.program_step import ProgramStep
from app.models.step import Step
from app.models.submission import Submission
from app.services.errors import ValidationFailed
from app.services.user_history_service import UserHistoryService

logger = logging.getLogger(__name__)


# ─── Paths ───────────────────────────────────────────────────────────────────

def _instance_path() -> str:
    return current_app.instance_path


def templates_dir_for(archive_id: int) -> str:
    """Directory that holds the blank template of an archive."""
    return os.path.join(_instance_path(), "uploads", "templates", "archives", str(archive_id))


def allowed_template_ext() -> Set[str]:
    """Extensions accepted for a template (same as documents)."""
    return set(current_app.config.get('ALLOWED_DOC_EXT', {'pdf', 'doc', 'docx'}))


def template_abs_path(archive: Archive) -> tuple[Optional[str], Optional[str]]:
    """(absolute path, basename) of the archive's template, or (None, None)."""
    if not archive.file_path:
        return None, None
    fpath = archive.file_path
    abs_path = os.path.join(_instance_path(), fpath) if not os.path.isabs(fpath) else fpath
    return abs_path, os.path.basename(abs_path)


# ─── Scope sets ──────────────────────────────────────────────────────────────

def permitted_step_ids(accessible_pids) -> Set[int]:
    """
    Step ids a caller can SEE in the catalog.

    `accessible_pids` is `User.get_accessible_program_ids()`: None (global)
    sees every step; otherwise the steps hooked to any of their programs.
    This is NOT a write permission — see `exclusive_step_ids`.
    """
    if accessible_pids is None:
        return set(db.session.execute(select(Step.id)).scalars().all())
    if not accessible_pids:
        return set()
    step_ids = db.session.execute(
        select(ProgramStep.step_id).where(ProgramStep.program_id.in_(accessible_pids))
    ).scalars().all()
    return set(step_ids)


def exclusive_step_ids(accessible_pids) -> Optional[Set[int]]:
    """
    Step ids whose document catalog the caller may MODIFY.

    None means global scope (any step). A step is shared by design (the same
    `step_id` hangs from several programs through `program_step`), so
    "touches one of my programs" is not a partition: a step is writable only
    when ALL of its `ProgramStep` rows point to the caller's programs. A step
    with no ProgramStep belongs to nobody: fails closed.
    """
    if accessible_pids is None:
        return None
    accessible_pids = set(accessible_pids)
    if not accessible_pids:
        return set()

    rows = db.session.execute(
        select(ProgramStep.step_id, ProgramStep.program_id)
    ).all()

    programs_by_step: dict[int, Set[int]] = {}
    for step_id, program_id in rows:
        programs_by_step.setdefault(step_id, set()).add(program_id)

    return {
        step_id for step_id, pids in programs_by_step.items()
        if pids and pids <= accessible_pids
    }


# ─── Listings ────────────────────────────────────────────────────────────────

def list_archive_rows_with_step(permitted: Optional[Set[int]]) -> list:
    """Column rows (archive + step name) for `?include=step`; `permitted` None = all."""
    j = join(Archive, Step, Archive.step_id == Step.id)
    sel = select(
        Archive.id, Archive.uuid, Archive.name, Archive.description,
        Archive.is_uploadable, Archive.is_downloadable,
        Archive.step_id, Step.name.label("step_name"),
        Archive.file_path,
        getattr(Archive, "allow_coordinator_upload"),
        getattr(Archive, "allow_extension_request", None),
    ).select_from(j)
    if permitted is not None:
        sel = sel.where(Archive.step_id.in_(permitted))
    return db.session.execute(sel).all()


def list_archives(permitted: Optional[Set[int]]) -> list:
    """Archive entities; `permitted` None = all."""
    sel = select(Archive)
    if permitted is not None:
        sel = sel.where(Archive.step_id.in_(permitted))
    return db.session.execute(sel).scalars().all()


def list_step_rows(permitted: Optional[Set[int]]) -> list:
    """(id, name, phase_id, phase_name) rows ordered by phase and step."""
    j = join(Step, Phase, Step.phase_id == Phase.id)
    sel = select(
        Step.id, Step.name, Step.phase_id, Phase.name.label("phase_name")
    ).select_from(j)
    if permitted is not None:
        sel = sel.where(Step.id.in_(permitted))
    return db.session.execute(sel.order_by(Phase.id, Step.id)).all()


def count_submissions(archive_id: int) -> int:
    """Number of submissions that depend on the archive."""
    return db.session.execute(
        select(func.count(Submission.id)).where(Submission.archive_id == archive_id)
    ).scalar_one()


# ─── Writes ──────────────────────────────────────────────────────────────────

def create_archive(*, name: str, step_id: int, description, is_downloadable: bool,
                   is_uploadable: bool, allow_coordinator_upload: bool,
                   allow_extension_request: bool, actor_id: int) -> Archive:
    """Create an archive and log it in the actor's history."""
    a = Archive(
        name=name,
        description=description,
        file_path=None,
        step_id=step_id,
        is_downloadable=is_downloadable,
        is_uploadable=is_uploadable,
    )
    if hasattr(Archive, "allow_coordinator_upload"):
        a.allow_coordinator_upload = allow_coordinator_upload
    if hasattr(Archive, "allow_extension_request"):
        setattr(a, "allow_extension_request", allow_extension_request)

    db.session.add(a)
    db.session.commit()

    try:
        step = db.session.get(Step, step_id)
        step_name = step.name if step else f"Step ID {step_id}"
        UserHistoryService.log_archive_created(actor_id, name, step_name)
        db.session.commit()
    except Exception as e:  # history must never fail the creation
        logger.error(f"Error al registrar creación de archivo en historial: {e}")
    return a


def update_archive(archive: Archive, fields: dict, *, actor_id: int) -> Archive:
    """
    Apply the PRESENT keys of `fields` (name, description, step_id and the four
    toggles) to the archive, commit and log what changed.

    Rolls back and re-raises on any failure.
    """
    a = archive
    try:
        changes = {}

        if "name" in fields and fields["name"] and fields["name"].strip():
            new_name = fields["name"].strip()
            if new_name != a.name:
                changes['name'] = {'old': a.name, 'new': new_name}
            a.name = new_name
        if "description" in fields:
            if fields["description"] != a.description:
                changes['description'] = {'old': a.description, 'new': fields["description"]}
            a.description = fields["description"]
        if "step_id" in fields and fields["step_id"]:
            new_step_id = int(fields["step_id"])
            if new_step_id != a.step_id:
                old_step = db.session.get(Step, a.step_id)
                new_step = db.session.get(Step, new_step_id)
                changes['step'] = {
                    'old': old_step.name if old_step else f"Step {a.step_id}",
                    'new': new_step.name if new_step else f"Step {new_step_id}"
                }
            a.step_id = new_step_id

        if "is_uploadable" in fields:
            new_value = bool(fields["is_uploadable"])
            if new_value != a.is_uploadable:
                changes['is_uploadable'] = {'old': a.is_uploadable, 'new': new_value}
            a.is_uploadable = new_value
        if "is_downloadable" in fields:
            new_value = bool(fields["is_downloadable"])
            if new_value != a.is_downloadable:
                changes['is_downloadable'] = {'old': a.is_downloadable, 'new': new_value}
            a.is_downloadable = new_value
        if "allow_coordinator_upload" in fields and hasattr(Archive, "allow_coordinator_upload"):
            new_value = bool(fields["allow_coordinator_upload"])
            old_value = getattr(a, 'allow_coordinator_upload', False)
            if new_value != old_value:
                changes['allow_coordinator_upload'] = {'old': old_value, 'new': new_value}
            a.allow_coordinator_upload = new_value
        if "allow_extension_request" in fields and hasattr(Archive, "allow_extension_request"):
            new_value = bool(fields["allow_extension_request"])
            old_value = getattr(a, 'allow_extension_request', False)
            if new_value != old_value:
                changes['allow_extension_request'] = {'old': old_value, 'new': new_value}
            setattr(a, "allow_extension_request", new_value)

        db.session.commit()

        if changes:
            try:
                step = db.session.get(Step, a.step_id)
                step_name = step.name if step else f"Step ID {a.step_id}"
                UserHistoryService.log_archive_updated(actor_id, a.name, step_name, changes)
                db.session.commit()
            except Exception as e:  # history must never fail the update
                logger.error(f"Error al registrar actualización de archivo en historial: {e}")
        return a
    except Exception:
        db.session.rollback()
        raise


def _delete_archive_files(archive_id: int) -> None:
    """Remove the template directory and the submission files of an archive."""
    templates_dir = templates_dir_for(archive_id)
    if os.path.isdir(templates_dir):
        try:
            shutil.rmtree(templates_dir)
        except OSError as e:
            logger.error(f"Error borrando el directorio de plantillas {templates_dir}: {e}")

    submissions = db.session.execute(
        select(Submission).where(Submission.archive_id == archive_id)
    ).scalars().all()
    for sub in submissions:
        if sub.file_path:
            abs_submission_path = os.path.join(_instance_path(), sub.file_path)
            if os.path.isfile(abs_submission_path):
                try:
                    os.remove(abs_submission_path)
                except OSError as e:
                    logger.error(f"Error borrando el archivo de submission {abs_submission_path}: {e}")


def delete_archive(archive: Archive, *, force: bool, actor_id: int) -> None:
    """Delete the archive (files first, then the row) and log it.

    Rolls back and re-raises on any failure.
    """
    try:
        archive_name = archive.name
        archive_description = archive.description

        # Files go BEFORE the commit: if this fails the row is not lost.
        _delete_archive_files(archive.id)

        # DB cascade removes the submission rows.
        db.session.delete(archive)
        db.session.commit()

        UserHistoryService.log_archive_deleted(
            actor_id, archive_name, archive_description, force
        )
    except Exception:
        db.session.rollback()
        raise


def _store_template(archive: Archive, file_storage) -> tuple[str, str]:
    """Save a template file on disk; raises ValidationFailed on a bad extension."""
    filename = file_storage.filename or ''
    if '.' not in filename:
        raise ValidationFailed("El archivo no tiene extensión.")
    ext = filename.rsplit('.', 1)[1].lower()

    # Mandatory whitelist: without it any extension could be written under
    # instance/uploads/templates.
    allowed = allowed_template_ext()
    if ext not in allowed:
        raise ValidationFailed(
            "Extensión no permitida. Solo se aceptan: "
            + ", ".join(sorted(allowed))
            + "."
        )

    templates_dir = templates_dir_for(archive.id)
    os.makedirs(templates_dir, exist_ok=True)
    base_name = secure_filename(archive.name)
    final_filename = f"{base_name}.{ext}"
    abs_path = os.path.join(templates_dir, final_filename)
    file_storage.save(abs_path)
    rel_path = os.path.relpath(abs_path, _instance_path())
    return rel_path, final_filename


def upload_template(archive: Archive, file_storage, *, actor_id: int) -> str:
    """Store the template, point the archive at it and log it. Returns the file name.

    Raises ValidationFailed for a bad file (nothing changed); rolls back and
    re-raises any other failure.
    """
    try:
        had_previous_template = bool(archive.file_path)

        rel_path, fname = _store_template(archive, file_storage)
        archive.file_path = rel_path
        db.session.commit()

        UserHistoryService.log_template_uploaded(
            actor_id, archive.name, fname, had_previous_template
        )
        return fname
    except ValidationFailed:
        raise
    except Exception:
        db.session.rollback()
        raise

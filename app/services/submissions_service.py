"""Applicant-side document submissions (upload / delete own submission).

Reviewer-side logic lives in `review_service`. Everything here is
framework-agnostic: the route passes the user and the raw inputs.
"""
from __future__ import annotations

import logging

from app import db
from app.models import Archive, Program, ProgramStep, Submission, UserProgram
from app.services.admission_service import get_admission_state
from app.services.errors import ConflictError, DomainError, NotFoundError
from app.services.user_history_service import UserHistoryService
from app.utils.files import save_user_doc

logger = logging.getLogger(__name__)

#: Denial text for DELETE /submissions/<uuid>. One string for every cause.
SUBMISSION_NOT_FOUND_MESSAGE = "Submission no encontrada"


class SubmissionError(DomainError):
    """Base of the errors raised by the submissions service."""


class NotEnrolled(SubmissionError):
    status_code = 403
    code = 'NOT_ENROLLED'


class StepLocked(ConflictError):
    code = 'STEP_LOCKED'
    level = 'danger'


def upload_submission(user, archive_uuid, program_id, program_slug, file):
    """Store (or replace) the applicant's file for an archive of a program.

    Args:
        user: the uploading applicant (needs id, role, names, uuid).
        archive_uuid: public UUID of the Archive.
        program_id / program_slug: one of them identifies the program.
        file: werkzeug FileStorage.

    Returns:
        (submission, archive, program, program_step)

    Raises SubmissionError subclasses with the codes the UI branches on:
    BAD_REQUEST 400, PROGRAM_NOT_FOUND 404, STEP_NOT_IN_PROGRAM 409,
    NOT_ENROLLED 403, STEP_LOCKED 409.
    """
    archive = Archive.by_uuid(archive_uuid)

    if not archive or not file or (not program_id and not program_slug):
        raise SubmissionError(
            "Faltan parámetros (archive_id, file, program_id/slug).", code='BAD_REQUEST')

    program = (db.session.get(Program, program_id) if program_id
               else Program.query.filter_by(slug=program_slug).first())
    if not program:
        raise NotFoundError("Programa no encontrado.", code='PROGRAM_NOT_FOUND')

    # There is one ProgramStep per (program_id, step_id).
    ps = ProgramStep.query.filter_by(program_id=program.id, step_id=archive.step_id).first()
    if not ps:
        raise ConflictError("El documento no pertenece a este programa.", code='STEP_NOT_IN_PROGRAM')

    up = UserProgram.query.filter_by(program_id=program.id, user_id=user.id).first()
    logger.info(
        f"[upload_submission] user={user.id} program={program.id if program else None} "
        f"archive={archive.id} step={archive.step_id} ps={ps.id if ps else None} up={bool(up)}"
    )
    if not up:
        raise NotEnrolled("Debes inscribirte antes de subir documentos.")

    # Lock check according to the admission state of the chosen program.
    state = get_admission_state(user.id, program.id, up)
    if state["lock_info"].get(archive.step_id or archive.step.id):
        raise StepLocked("Debes aprobar el paso anterior.")

    rel = save_user_doc(file, user.id, phase='admission', name=archive.name)

    # Reuse the existing submission or create one.
    existing = state["subs"].get(archive.id)
    sub = existing or Submission(
        user_id=user.id,
        archive_id=archive.id,
        program_step_id=ps.id,
        file_path=rel,
        semester=0,
        uploaded_by=user.id,
        uploaded_by_role=user.role.name,
        status='pending'
    )
    sub.program_step_id = ps.id
    sub.upload_date = db.func.now()
    sub.file_path = rel
    sub.status = 'pending'

    db.session.add(sub)
    db.session.commit()

    # History (best effort).
    try:
        UserHistoryService.log_document_upload(
            user_id=user.id,
            archive_name=archive.name,
            program_name=program.name,
            uploaded_by_admin=False
        )
        db.session.commit()
    except Exception as e:
        logger.error(f"Error al registrar subida de documento en historial: {e}")

    # Notify the program coordinator (best effort).
    try:
        from app.services.notification_service import NotificationService
        if program.coordinator_id:
            student_name = f"{user.first_name} {user.last_name}"
            NotificationService.create_notification(
                user_id=program.coordinator_id,
                notification_type='document_submitted',
                title='Nuevo documento recibido',
                message=f'{student_name} ha subido el documento "{archive.name}" en {program.name}.',
                priority='low',
                action_url='/admin/review',
                data={'student_id': user.id, 'program_id': program.id},
            )
            db.session.commit()
    except Exception as e:
        logger.error(f"Error al notificar subida de documento: {e}")

    return sub, archive, program, ps


def delete_own_submission(user_id: int, sub_uuid) -> None:
    """Delete the caller's own submission and log it in the history.

    "Does not exist" and "is not yours" raise the SAME NotFoundError (same
    status, same message) so the endpoint is not an enumeration oracle.
    """
    sub = Submission.by_uuid(sub_uuid)
    if not sub or sub.user_id != user_id:
        raise NotFoundError(SUBMISSION_NOT_FOUND_MESSAGE)

    archive_name = sub.archive.name if sub.archive else "Desconocido"
    program_name = "Desconocido"
    if sub.program_step and sub.program_step.program:
        program_name = sub.program_step.program.name

    db.session.delete(sub)
    db.session.commit()

    try:
        UserHistoryService.log_document_deletion(
            user_id=user_id,
            archive_name=archive_name,
            program_name=program_name,
            deleted_by_admin=False
        )
        db.session.commit()
    except Exception as e:
        logger.error(f"Error al registrar eliminación de documento en historial: {e}")

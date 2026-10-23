"""
Admission documents delivered late under an extension (prórroga) — owner's
decision 5 of phase 6C.

A granted extension (`ExtensionRequest.status == 'granted'`) lets a student
enroll without an admission document. Once `granted_until` passes and the
document is still not delivered — no submission of that archive for the
student program in status pending/review/approved (a rejected one counts as
not delivered) — the student owes it, and the debt blocks re-enrolling in the
next semester (`semester_transition_service.evaluate_student` and
`permanence_service.confirm_semester_enrollment`) until it is delivered.

An enrolled student sees these documents on their dashboard and uploads them
through the regular admission upload (`submissions_service.upload_submission`);
only archives with a granted extension are open to them.

Framework-agnostic: callers pass the user / ids explicitly.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import or_

from app import db
from app.models import Archive, ExtensionRequest, Phase, ProgramStep, Step, Submission, UserProgram
from app.services.errors import ConflictError, DomainError, NotFoundError
from app.utils.datetime_utils import now_local, to_local_timezone

#: Submission statuses that count as delivered (a rejected one does not).
DELIVERED_STATUSES = frozenset({'pending', 'review', 'approved'})

DOCUMENT_NOT_FOUND_MESSAGE = 'Documento no encontrado.'


class AdmissionDebtError(DomainError):
    """The student owes admission documents whose extension lapsed."""


def _latest_submission(up: UserProgram, archive_id: int) -> Optional[Submission]:
    return (
        Submission.query
        .outerjoin(ProgramStep, Submission.program_step_id == ProgramStep.id)
        .filter(Submission.archive_id == archive_id,
                or_(Submission.user_program_id == up.id,
                    (Submission.user_id == up.user_id)
                    & (ProgramStep.program_id == up.program_id)))
        .order_by(Submission.upload_date.desc(), Submission.id.desc())
        .first()
    )


def extension_documents(up: Optional[UserProgram]) -> list:
    """
    Admission documents of the student program covered by a granted
    extension, one per archive (the latest `granted_until`):

    [{'archive', 'program_step', 'extension', 'granted_until' (local),
      'submission', 'delivered', 'overdue'}]
    """
    if up is None:
        return []
    rows = (
        ExtensionRequest.query
        .join(ProgramStep, ExtensionRequest.program_step_id == ProgramStep.id)
        .join(Step, ProgramStep.step_id == Step.id)
        .join(Phase, Step.phase_id == Phase.id)
        .filter(ExtensionRequest.user_id == up.user_id,
                ExtensionRequest.status == 'granted',
                ExtensionRequest.granted_until.isnot(None),
                ProgramStep.program_id == up.program_id,
                Phase.name == 'admission')
        .order_by(ExtensionRequest.granted_until.desc(), ExtensionRequest.id.desc())
        .all()
    )
    now = now_local()
    seen, docs = set(), []
    for ext in rows:
        if ext.archive_id in seen or ext.archive is None:
            continue
        seen.add(ext.archive_id)
        sub = _latest_submission(up, ext.archive_id)
        delivered = sub is not None and sub.status in DELIVERED_STATUSES
        granted_until = to_local_timezone(ext.granted_until)
        docs.append({
            'archive': ext.archive,
            'program_step': ext.program_step,
            'extension': ext,
            'granted_until': granted_until,
            'submission': sub,
            'delivered': delivered,
            'overdue': granted_until < now and not delivered,
        })
    return docs


def overdue_admission_documents(up: Optional[UserProgram]) -> list:
    """The `extension_documents` whose extension lapsed undelivered."""
    return [d for d in extension_documents(up) if d['overdue']]


def debt_message(docs: list) -> str:
    names = ', '.join(d['archive'].name for d in docs)
    return ('No puede inscribirse al siguiente semestre: tiene documentos de admisión con '
            f'prórroga vencida sin entregar: {names}.')


def require_no_debt(up: UserProgram) -> None:
    """Raise AdmissionDebtError when the student owes overdue admission documents."""
    docs = overdue_admission_documents(up)
    if docs:
        raise AdmissionDebtError(debt_message(docs),
                                 fields={'documents': [d['archive'].name for d in docs]})


def pending_extension_documents(up: Optional[UserProgram]) -> list:
    """What an enrolled student still has to upload: covered by an extension and
    not delivered, or delivered but rejected (pending ones may be replaced)."""
    return [d for d in extension_documents(up)
            if d['submission'] is None or d['submission'].status != 'approved']


def upload_extension_document(user, user_program_id: int, archive_uuid, file):
    """
    An enrolled student uploads an admission document covered by a granted
    extension. Goes through the regular admission upload (same validation,
    history and coordinator notice). Returns the Submission.
    """
    from app.services import submissions_service

    up = db.session.get(UserProgram, user_program_id) if user_program_id else None
    if up is None or up.user_id != user.id or up.admission_status != 'enrolled':
        raise NotFoundError(DOCUMENT_NOT_FOUND_MESSAGE)
    archive = Archive.by_uuid(archive_uuid)
    doc = next((d for d in extension_documents(up)
                if archive is not None and d['archive'].id == archive.id), None)
    if doc is None:
        raise NotFoundError(DOCUMENT_NOT_FOUND_MESSAGE)
    if doc['submission'] is not None and doc['submission'].status == 'approved':
        raise ConflictError('Este documento ya fue aprobado.')
    if file is None:
        raise DomainError('Selecciona un archivo.')

    sub, archive, program, _ps = submissions_service.upload_submission(
        user, archive.uuid, up.program_id, None, file)
    submissions_service.notify_new_submission(user, sub, archive, program)
    return sub

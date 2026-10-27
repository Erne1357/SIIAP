"""
Admission documents delivered late under an extension (prórroga) — owner's
decision 5 of phase 6C.

A granted extension (`ExtensionRequest.status == 'granted'`) lets a student
enroll without an admission document. Once `granted_until` passes and the
document is still not delivered — no submission of that archive for the
student program in status pending/review/approved (a rejected one counts as
not delivered) — the student owes it. So does a document whose extension was
`rejected` (also one rejected while the student was still an applicant, and
one whose grant was reverted to rejected): the document was due. Per archive
and student program the latest decided request (granted or rejected) wins, so
a later grant that has not lapsed lifts the block. The debt blocks
re-enrolling in the next semester (`semester_transition_service.evaluate_student` and
`permanence_service.confirm_semester_enrollment`) until it is delivered.

An enrolled student sees these documents on their dashboard and uploads them
through the regular admission upload (`submissions_service.upload_submission`);
only archives whose latest extension decision is a grant or a rejection are
open to them.

Framework-agnostic: callers pass the user / ids explicitly.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, func, or_

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
    Admission documents of the student program covered by an extension
    decision, one per archive (the latest decided request, granted or
    rejected, wins):

    [{'archive', 'program_step', 'extension', 'granted_until' (local; None when
      the request was rejected), 'rejected', 'submission', 'delivered',
      'overdue'}]

    A rejected request is overdue while the document is not delivered; a
    granted one once `granted_until` passed.
    """
    if up is None:
        return []
    rows = (
        ExtensionRequest.query
        .join(ProgramStep, ExtensionRequest.program_step_id == ProgramStep.id)
        .join(Step, ProgramStep.step_id == Step.id)
        .join(Phase, Step.phase_id == Phase.id)
        .filter(or_(ExtensionRequest.user_program_id == up.id,
                    and_(ExtensionRequest.user_program_id.is_(None),
                         ExtensionRequest.user_id == up.user_id,
                         ProgramStep.program_id == up.program_id)),
                or_(and_(ExtensionRequest.status == 'granted',
                         ExtensionRequest.granted_until.isnot(None)),
                    ExtensionRequest.status == 'rejected'),
                Phase.name == 'admission')
        .order_by(func.coalesce(ExtensionRequest.decided_at, ExtensionRequest.created_at).desc(),
                  ExtensionRequest.id.desc())
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
        rejected = ext.status == 'rejected'
        granted_until = None if rejected else to_local_timezone(ext.granted_until)
        docs.append({
            'archive': ext.archive,
            'program_step': ext.program_step,
            'extension': ext,
            'granted_until': granted_until,
            'rejected': rejected,
            'submission': sub,
            'delivered': delivered,
            'overdue': not delivered and (rejected or granted_until < now),
        })
    return docs


def overdue_admission_documents(up: Optional[UserProgram]) -> list:
    """The `extension_documents` whose extension lapsed undelivered."""
    return [d for d in extension_documents(up) if d['overdue']]


def debt_message(docs: list) -> str:
    names = ', '.join(d['archive'].name for d in docs)
    return ('No puede inscribirse al siguiente semestre: tiene documentos de admisión con '
            f'prórroga vencida o rechazada sin entregar: {names}.')


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
    An enrolled student uploads an admission document covered by an extension
    decision. Goes through the regular admission upload (same validation,
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

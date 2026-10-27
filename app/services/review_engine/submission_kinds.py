"""
Review kinds backed by `Submission` (phase 6D): admission documents,
permanence documents, temporary-leave requests and conclusion requirements.

The kind of a submission comes from its archive: `archive_key ==
'leave_request'` is a leave request; otherwise the phase of the archive's
step decides (admission / permanence / conclusion).

Each kind keeps the side effects its legacy service had:
- admission_doc / conclusion_doc (`review_service.decide_submission`):
  `log_document_review`, `notify_document_approved|rejected`, socket
  `submission:reviewed`; an approval meets the linked admission conditions
  (`conclusion_service.on_requirement_approved`), a reverted approval
  reopens them.
- permanence_doc (`permanence_service.review_permanence_document`):
  notices `permanence_doc_approved|rejected`, e-mail on rejection, history
  `permanence_document_<status>`, socket `permanence:status_changed`.
- leave_request (`permanence_service.process_leave_request`): an approval
  puts the active semester enrollment `on_leave` and the student program
  `on_leave`; reverting it is allowed only while that period's enrollment is
  still `on_leave`, and restores `active`.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app import db
from app.models import Archive, Phase, ProgramStep, Step, Submission, User, UserProgram
from app.models.semester_enrollment import SemesterEnrollment
from app.services import academic_progress
from app.services import academic_status_service
from app.services import file_access_service
from app.services import public_id_service
from app.services.notification_service import NotificationService
from app.services.review_engine.base import ReviewKind
from app.services.review_engine.errors import ReviewConflict
from app.services.review_engine.registry import register
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local

logger = logging.getLogger(__name__)

LEAVE_ARCHIVE_KEY = 'leave_request'

#: Phase name -> kind key, for submissions that are not leave requests.
KIND_BY_PHASE = {
    'admission': 'admission_doc',
    'permanence': 'permanence_doc',
    'conclusion': 'conclusion_doc',
}

LEAVE_REVERT_CONFLICT_MESSAGE = (
    'La inscripción del periodo ya cambió; la baja temporal no se puede revertir.'
)


def kind_key_for_submission(submission) -> Optional[str]:
    """Kind key of `submission` (None when its archive or phase is unknown)."""
    archive = getattr(submission, 'archive', None)
    if archive is None:
        return None
    if archive.archive_key == LEAVE_ARCHIVE_KEY:
        return 'leave_request'
    step = archive.step
    phase = step.phase if step is not None else None
    return KIND_BY_PHASE.get(phase.name) if phase is not None else None


def kind_for_submission(submission) -> Optional[ReviewKind]:
    """Registered kind instance of `submission`, or None."""
    from app.services.review_engine.registry import KINDS
    return KINDS.get(kind_key_for_submission(submission))


def lock_submission(submission_id) -> Optional[Submission]:
    """The submission with internal id `submission_id`, row-locked and refreshed."""
    if submission_id is None:
        return None
    return (Submission.query.filter_by(id=submission_id)
            .with_for_update().populate_existing().first())


def _full_name(user) -> str:
    if user is None:
        return ''
    return f"{user.first_name} {user.last_name} {user.mother_last_name or ''}".strip()


class SubmissionKind(ReviewKind):
    """Common behaviour of every Submission-backed kind."""

    model = Submission
    pending_statuses = ('pending', 'review')
    decided_statuses = ('approved', 'rejected')
    not_found_message = 'Documento no encontrado.'
    #: Value stored as `reviewer_comment` when the comment is empty.
    empty_comment: Optional[str] = ''

    # ── Loading ──────────────────────────────────────────────────────────

    def load_for_update(self, item_uuid):
        row = Submission.by_uuid(item_uuid)
        if row is None:
            return None
        sub = lock_submission(row.id)
        return sub if self.matches(sub) else None

    def matches(self, item) -> bool:
        return item is not None and kind_key_for_submission(item) == self.key

    # ── Ownership ────────────────────────────────────────────────────────

    def program_id(self, item) -> Optional[int]:
        if item is None or item.program_step is None:
            return None
        return item.program_step.program_id

    def user_program_id(self, item) -> Optional[int]:
        if item is None:
            return None
        if item.user_program_id is not None:
            return item.user_program_id
        program_id = self.program_id(item)
        if program_id is None:
            return None
        up = UserProgram.query.filter_by(user_id=item.user_id, program_id=program_id).first()
        return up.id if up else None

    def student(self, item):
        return item.user

    # ── Decision ─────────────────────────────────────────────────────────

    def apply(self, item, status, actor, comment, extra) -> None:
        item.status = status
        item.reviewer_id = actor.id
        item.review_date = now_local()
        item.reviewer_comment = comment or self.empty_comment

    def on_approved(self, item, actor) -> None:
        # Phase 6C: approving the requirement a pending admission condition
        # points at fulfils that condition (same transaction).
        from app.services import conclusion_service
        conclusion_service.on_requirement_approved(item, actor.id)

    def on_reverted(self, item, actor) -> None:
        from app.services import conclusion_service
        conclusion_service.reopen_conditions_for_submission(item, actor.id)

    # ── Inbox ────────────────────────────────────────────────────────────

    def _kind_filter(self, query):
        raise NotImplementedError

    def _base_query(self, program_ids):
        q = (Submission.query
             .join(ProgramStep, Submission.program_step_id == ProgramStep.id)
             .join(Archive, Submission.archive_id == Archive.id)
             .join(Step, Archive.step_id == Step.id)
             .join(Phase, Step.phase_id == Phase.id))
        q = self._kind_filter(q)
        if program_ids is not None:
            q = q.filter(ProgramStep.program_id.in_(program_ids))
        return q

    def pending_query(self, program_ids):
        return (self._base_query(program_ids)
                .filter(Submission.status.in_(self.pending_statuses))
                .order_by(Submission.upload_date.asc(), Submission.id.asc()))

    def decided_query(self, program_ids, since: datetime):
        return (self._base_query(program_ids)
                .filter(Submission.status.in_(self.decided_statuses),
                        Submission.review_date.isnot(None),
                        Submission.review_date >= since)
                .order_by(Submission.review_date.desc(), Submission.id.desc()))

    submitted_attr = 'upload_date'
    decided_attr = 'review_date'

    def row_load_options(self):
        return (
            joinedload(Submission.user),
            joinedload(Submission.archive),
            joinedload(Submission.document_deadline),
            joinedload(Submission.program_step).joinedload(ProgramStep.program),
        )

    def title(self, item) -> str:
        if item.archive is not None:
            return item.archive.name
        return f'Documento ID {item.archive_id}'

    def submitted_at(self, item):
        return item.upload_date

    def decided_at(self, item):
        return item.review_date

    def row(self, item) -> dict:
        user = item.user
        program = item.program_step.program if item.program_step else None
        return {
            'uuid': str(item.uuid),
            'kind': self.key,
            'kind_label': self.label,
            'student_name': _full_name(user),
            'student_uuid': public_id_service.user_uuid(item.user_id),
            'program_id': program.id if program else None,
            'program_name': program.name if program else None,
            'title': self.title(item),
            'uploaded_at': self.submitted_at(item),
            'file_url': file_access_service.submission_file_url(item),
            'file_path': item.file_path,  # stored path: the inbox checks it on disk
            'status': item.status,
            'decided_at': self.decided_at(item),
            'comment': item.reviewer_comment,
        }


def _not_leave():
    return or_(Archive.archive_key.is_(None), Archive.archive_key != LEAVE_ARCHIVE_KEY)


class _ReviewInboxSubmissionKind(SubmissionKind):
    """admission_doc / conclusion_doc: the legacy `admin/review` behaviour."""

    permission = 'admin_review.api.decide'
    phase_name = ''

    def _kind_filter(self, query):
        return query.filter(Phase.name == self.phase_name, _not_leave())

    def log_decision(self, item, status, actor, comment) -> None:
        # Kept as before 6D: log_document_review also sends its own notice.
        UserHistoryService.log_document_review(
            user_id=item.user_id,
            archive_name=self.title(item),
            status=status,
            reviewer_comment=comment,
            admin_id=actor.id,
            user_program_id=self.user_program_id(item),
        )

    def notify(self, item, status, reverted) -> None:
        program = item.program_step.program if item.program_step else None
        program_slug = program.slug if program else None
        if status == 'approved':
            NotificationService.notify_document_approved(
                item.user_id, self.title(item), item.id, program_slug=program_slug)
        else:
            NotificationService.notify_document_rejected(
                item.user_id, self.title(item), item.id, item.reviewer_comment,
                program_slug=program_slug)

    def emit(self, item, status, reverted) -> None:
        from app.sockets.emitters import emit_user_and_coordinators

        program_id = self.program_id(item)
        emit_user_and_coordinators(
            'submission:reviewed',
            {
                'user_id': public_id_service.user_uuid(item.user_id),
                'submission_id': public_id_service.submission_uuid(item.id),
                'archive_id': public_id_service.archive_uuid(item.archive_id),
                'program_id': program_id,
                'status': status,
            },
            user_id=item.user_id,
            program_id=program_id,
        )


class AdmissionDocKind(_ReviewInboxSubmissionKind):
    key = 'admission_doc'
    label = 'Documento de admisión'
    phase_name = 'admission'


class ConclusionDocKind(_ReviewInboxSubmissionKind):
    key = 'conclusion_doc'
    label = 'Requisito de conclusión'
    phase_name = 'conclusion'


class PermanenceDocKind(SubmissionKind):
    key = 'permanence_doc'
    label = 'Documento de permanencia'
    permission = 'permanence.api.review_doc'
    empty_comment = None

    def _kind_filter(self, query):
        return query.filter(Phase.name == 'permanence', _not_leave())

    def title(self, item) -> str:
        if item.document_deadline is not None:
            return item.document_deadline.label
        return super().title(item)

    def log_decision(self, item, status, actor, comment) -> None:
        verb = 'Aprobó' if status == 'approved' else 'Rechazó'
        UserHistoryService.log_action(
            user_id=item.user_id,
            admin_id=actor.id,
            action=f'permanence_document_{status}',
            details=f'{verb} "{self.title(item)}". {comment or ""}',
            user_program_id=self.user_program_id(item),
        )

    def notify(self, item, status, reverted) -> None:
        label = self.title(item)
        notes = item.reviewer_comment
        if status == 'approved':
            NotificationService.create_notification(
                user_id=item.user_id,
                notification_type='permanence_doc_approved',
                title=f'Documento aprobado — {label}',
                message=f'Tu documento "{label}" fue aprobado para el periodo actual.',
                priority='medium',
                action_url='/user/dashboard',
            )
            return
        NotificationService.create_notification(
            user_id=item.user_id,
            notification_type='permanence_doc_rejected',
            title=f'Documento rechazado — {label}',
            message=(
                f'Tu documento "{label}" fue rechazado. '
                f'Motivo: {notes or "Sin especificar"}. '
                'Vuelve a subirlo cuando la ventana esté abierta.'
            ),
            priority='high',
            action_url='/user/dashboard',
        )
        try:
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            from app.utils.urls import external_url

            user = db.session.get(User, item.user_id)
            if user:
                # Pinned to APP_BASE_URL, never to the request host.
                subject, html = EmailTemplates.permanence_doc_rejected(
                    user_name=f'{user.first_name} {user.last_name}',
                    document_label=label,
                    reason=notes or 'Sin especificar',
                    dashboard_url=external_url('pages_user.dashboard'),
                )
                EmailService.queue_email(item.user_id, subject, html)
        except Exception as exc:
            logger.error('Error queueing email for permanence_doc_rejected: %s', exc)

    def emit(self, item, status, reverted) -> None:
        from app.sockets.emitters import emit_user_and_coordinators

        program_id = self.program_id(item)
        emit_user_and_coordinators(
            'permanence:status_changed',
            {
                'user_id': public_id_service.user_uuid(item.user_id),
                'submission_id': public_id_service.submission_uuid(item.id),
                'program_id': program_id,
                'action': 'doc_reviewed',
                'status': status,
                'document_label': self.title(item),
            },
            user_id=item.user_id,
            program_id=program_id,
        )


def _set_enrollment_status(enrollment: SemesterEnrollment, new_status: str) -> bool:
    """Move a semester enrollment along the allowed map; False if the move is not allowed."""
    if not academic_progress.can_change_enrollment_status(enrollment.status, new_status):
        return False
    enrollment.status = new_status
    return True


class LeaveRequestKind(SubmissionKind):
    key = 'leave_request'
    label = 'Solicitud de baja temporal'
    permission = 'permanence.api.review_doc'
    not_found_message = 'Solicitud no encontrada.'
    empty_comment = None

    def _kind_filter(self, query):
        return query.filter(Archive.archive_key == LEAVE_ARCHIVE_KEY)

    def title(self, item) -> str:
        return self.label

    def _user_program(self, item) -> Optional[UserProgram]:
        up_id = self.user_program_id(item)
        return db.session.get(UserProgram, up_id) if up_id else None

    def on_approved(self, item, actor) -> None:
        """The active semester enrollment goes on leave, and so does the student program."""
        up = self._user_program(item)
        if up is None:
            return
        active = (SemesterEnrollment.query
                  .filter_by(user_program_id=up.id, status='active')
                  .with_for_update().first())
        if active is None:
            return
        _set_enrollment_status(active, 'on_leave')
        if up.academic_status == academic_status_service.ACTIVE:
            academic_status_service.transition(
                up, academic_status_service.ON_LEAVE, actor_id=actor.id)

    def on_reverted(self, item, actor) -> None:
        """Back to active, only while the request's period is still on leave."""
        up = self._user_program(item)
        enrollment = None
        if up is not None and item.academic_period_id is not None:
            enrollment = (SemesterEnrollment.query
                          .filter_by(user_program_id=up.id,
                                     academic_period_id=item.academic_period_id)
                          .with_for_update().first())
        if enrollment is None or enrollment.status != 'on_leave':
            raise ReviewConflict(LEAVE_REVERT_CONFLICT_MESSAGE)
        _set_enrollment_status(enrollment, 'active')
        if up.academic_status == academic_status_service.ON_LEAVE:
            academic_status_service.transition(
                up, academic_status_service.ACTIVE, actor_id=actor.id)

    def log_decision(self, item, status, actor, comment) -> None:
        approved = status == 'approved'
        UserHistoryService.log_action(
            user_id=item.user_id,
            admin_id=actor.id,
            action='leave_request_approved' if approved else 'leave_request_rejected',
            details=(f'{"Aprobó" if approved else "Rechazó"} solicitud de baja temporal. '
                     f'{comment or ""}'),
            user_program_id=self.user_program_id(item),
        )

    def notify(self, item, status, reverted) -> None:
        approved = status == 'approved'
        notes = item.reviewer_comment
        if approved:
            NotificationService.create_notification(
                user_id=item.user_id,
                notification_type='leave_request_approved',
                title='Baja temporal aprobada',
                message=(
                    'Tu solicitud de baja temporal fue aprobada. '
                    'Tu estado se actualizó a baja temporal. '
                    'Para reincorporarte, contacta al coordinador.'
                ),
                priority='high',
                action_url='/user/dashboard',
            )
        else:
            NotificationService.create_notification(
                user_id=item.user_id,
                notification_type='leave_request_rejected',
                title='Baja temporal rechazada',
                message=(
                    'Tu solicitud de baja temporal fue rechazada. '
                    f'Motivo: {notes or "Sin especificar"}.'
                ),
                priority='high',
                action_url='/user/dashboard',
            )
        try:
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            from app.utils.urls import external_url

            user = db.session.get(User, item.user_id)
            if user:
                program = item.program_step.program if item.program_step else None
                subject, html = EmailTemplates.leave_request_result(
                    user_name=f'{user.first_name} {user.last_name}',
                    program_name=program.name if program else 'tu programa',
                    approved=approved,
                    reason=notes or '',
                    # Pinned to APP_BASE_URL, never to the request host.
                    dashboard_url=external_url('pages_user.dashboard'),
                )
                EmailService.queue_email(item.user_id, subject, html)
        except Exception as exc:
            logger.error('Error queueing email for leave_request_result: %s', exc)

    def emit(self, item, status, reverted) -> None:
        from app.sockets.emitters import emit_user_and_coordinators

        approved = status == 'approved'
        program_id = self.program_id(item)
        emit_user_and_coordinators(
            'permanence:status_changed',
            {
                'user_id': public_id_service.user_uuid(item.user_id),
                'submission_id': public_id_service.submission_uuid(item.id),
                'program_id': program_id,
                'action': 'leave_decided',
                'approved': approved,
                'new_enrollment_status': 'on_leave' if approved else None,
            },
            user_id=item.user_id,
            program_id=program_id,
        )


register(AdmissionDocKind())
register(PermanenceDocKind())
register(LeaveRequestKind())
register(ConclusionDocKind())

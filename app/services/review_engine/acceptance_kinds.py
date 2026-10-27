"""
Review kind backed by `AcceptanceDocument` (phase 6D): the enrollment receipt
(boleta / carta de número de control) the applicant uploads and the
coordinator approves or rejects.

Keeps every side effect of the legacy
`acceptance_service.review_enrollment_receipt`: history
`enrollment_receipt_<status>`, notice `enrollment_receipt_<status>`, e-mail to
the applicant and the `acceptance:updated` socket event on the user's room.
Reverting an approval is refused once the applicant is already `enrolled`.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.models import Program, User, UserProgram
from app.models.acceptance_document import AcceptanceDocument
from app.services import file_access_service
from app.services import public_id_service
from app.services.notification_service import NotificationService
from app.services.review_engine.base import ReviewKind
from app.services.review_engine.errors import ReviewConflict
from app.services.review_engine.registry import register
from app.services.user_history_service import UserHistoryService

logger = logging.getLogger(__name__)

RECEIPT_TYPE = 'enrollment_receipt'

ENROLLED_REVERT_MESSAGE = (
    'El aspirante ya está inscrito; la aprobación del recibo no se puede revertir.'
)


def _full_name(user) -> str:
    if user is None:
        return ''
    return f"{user.first_name} {user.last_name} {user.mother_last_name or ''}".strip()


class EnrollmentReceiptKind(ReviewKind):
    key = RECEIPT_TYPE
    label = 'Recibo de inscripción'
    permission = 'acceptance.api.review_doc'
    model = AcceptanceDocument
    pending_statuses = ('uploaded',)
    decided_statuses = ('approved', 'rejected')
    not_found_message = 'Documento no encontrado.'

    # ── Loading ──────────────────────────────────────────────────────────

    def load_for_update(self, item_uuid):
        row = AcceptanceDocument.by_uuid(item_uuid)
        if row is None:
            return None
        doc = (AcceptanceDocument.query.filter_by(id=row.id)
               .with_for_update().populate_existing().first())
        return doc if self.matches(doc) else None

    def matches(self, item) -> bool:
        return item is not None and item.document_type == RECEIPT_TYPE

    # ── Ownership ────────────────────────────────────────────────────────

    def program_id(self, item) -> Optional[int]:
        if item is None or item.user_program is None:
            return None
        return item.user_program.program_id

    def user_program_id(self, item) -> Optional[int]:
        return item.user_program_id if item is not None else None

    def student(self, item):
        return item.user_program.user

    # ── Decision ─────────────────────────────────────────────────────────

    def apply(self, item, status, actor, comment, extra) -> None:
        item.status = status
        item.reviewed_by_id = actor.id
        item.reviewed_at = self.now()
        item.review_notes = comment or None

    def on_reverted(self, item, actor) -> None:
        up = item.user_program
        if up is not None and up.admission_status == 'enrolled':
            raise ReviewConflict(ENROLLED_REVERT_MESSAGE)

    # ── After the commit ─────────────────────────────────────────────────

    def log_decision(self, item, status, actor, comment) -> None:
        program = item.user_program.program
        notes = item.review_notes or ''
        word = 'aprobada' if status == 'approved' else 'rechazada'
        UserHistoryService.log_action(
            user_id=item.user_program.user_id,
            admin_id=actor.id,
            action=f'enrollment_receipt_{status}',
            details=f'Carta {word} para {program.name}. {notes}',
        )

    def notify(self, item, status, reverted) -> None:
        up = item.user_program
        user_id = up.user_id
        program = up.program
        notes = item.review_notes
        if status == 'approved':
            NotificationService.create_notification(
                user_id=user_id,
                notification_type='enrollment_receipt_approved',
                title='Carta de número de control aprobada',
                message=f'Tu carta de asignación de número de control para {program.name} fue aprobada. '
                        f'El coordinador te asignará tu número de control próximamente.',
                priority='high',
                action_url='/user/dashboard',
            )
        else:
            NotificationService.create_notification(
                user_id=user_id,
                notification_type='enrollment_receipt_rejected',
                title='Carta de número de control rechazada',
                message=f'Tu carta de asignación de número de control para {program.name} fue rechazada. '
                        f'Motivo: {notes or "Sin especificar"}. Por favor vuelve a subirla.',
                priority='high',
                action_url='/user/dashboard',
            )

        try:
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            from app.utils.urls import external_url
            user = User.query.get(user_id)
            if user:
                # Pinned to APP_BASE_URL, never to the request host.
                dashboard_url = external_url('pages_user.dashboard')
                if status == 'approved':
                    subject, html = EmailTemplates.enrollment_receipt_approved(
                        user_name=f"{user.first_name} {user.last_name}",
                        program_name=program.name,
                        dashboard_url=dashboard_url,
                    )
                else:
                    subject, html = EmailTemplates.enrollment_receipt_rejected(
                        user_name=f"{user.first_name} {user.last_name}",
                        program_name=program.name,
                        reason=notes or "Sin especificar",
                        dashboard_url=dashboard_url,
                    )
                EmailService.queue_email(user_id, subject, html)
        except Exception as exc:
            logger.error('Error queueing email for enrollment_receipt_%s: %s', status, exc)

    def emit(self, item, status, reverted) -> None:
        from app.extensions import socketio

        up = item.user_program
        socketio.emit('acceptance:updated', {
            'user_id': public_id_service.user_uuid(up.user_id),
            'program_id': up.program_id,
            'action': f'receipt_{status}',
        }, room=f'user:{up.user_id}')

    # ── Inbox ────────────────────────────────────────────────────────────

    def _base_query(self, program_ids):
        q = (AcceptanceDocument.query
             .join(UserProgram, AcceptanceDocument.user_program_id == UserProgram.id)
             .filter(AcceptanceDocument.document_type == RECEIPT_TYPE))
        if program_ids is not None:
            q = q.filter(UserProgram.program_id.in_(program_ids))
        return q

    def pending_query(self, program_ids):
        return (self._base_query(program_ids)
                .filter(AcceptanceDocument.status.in_(self.pending_statuses))
                .order_by(AcceptanceDocument.uploaded_at.asc(), AcceptanceDocument.id.asc()))

    def decided_query(self, program_ids, since: datetime):
        return (self._base_query(program_ids)
                .filter(AcceptanceDocument.status.in_(self.decided_statuses),
                        AcceptanceDocument.reviewed_at.isnot(None),
                        AcceptanceDocument.reviewed_at >= since)
                .order_by(AcceptanceDocument.reviewed_at.desc(), AcceptanceDocument.id.desc()))

    def title(self, item) -> str:
        return self.label

    def submitted_at(self, item):
        return item.uploaded_at

    def decided_at(self, item):
        return item.reviewed_at

    def row(self, item) -> dict:
        up = item.user_program
        user = up.user if up else None
        program = Program.query.get(up.program_id) if up else None
        return {
            'uuid': str(item.uuid),
            'kind': self.key,
            'kind_label': self.label,
            'student_name': _full_name(user),
            'student_uuid': public_id_service.user_uuid(up.user_id) if up else None,
            'program_id': program.id if program else None,
            'program_name': program.name if program else None,
            'title': self.title(item),
            'uploaded_at': self.submitted_at(item),
            'file_url': file_access_service.acceptance_document_url(item),
            'status': item.status,
            'decided_at': self.decided_at(item),
            'comment': item.review_notes,
        }


register(EnrollmentReceiptKind())

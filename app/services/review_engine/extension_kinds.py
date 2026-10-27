"""
Review kind backed by `ExtensionRequest` (phase 6D): an extension (prórroga)
of an admission document's deadline.

Decisions: approve -> `granted` (needs `extra['granted_until']`, optional
`extra['condition_text']`), reject -> `rejected`. The request is addressed by
its public `uuid`.

Side effects kept from `ExtensionsService.decide_request`: history entry of
the admin + notice to the student (`log_extension_decision`), socket
`extension:decided`. The admission debt blocking enrollment is computed live
from `granted_until` (`admission_debt_service`), so reverting a grant needs no
extra undo here.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import func

from app import db
from app.models import Program, ProgramStep, UserProgram
from app.models.extension_request import ExtensionRequest
from app.services import public_id_service
from app.services.notification_service import NotificationService
from app.services.review_engine.base import ReviewKind
from app.services.review_engine.errors import ReviewConflict
from app.services.review_engine.registry import register
from app.services.user_history_service import UserHistoryService

GRANTED_UNTIL_REQUIRED_MESSAGE = 'Indica la fecha límite de la prórroga.'
CANCELLED_MESSAGE = 'La solicitud fue cancelada; ya no se puede decidir.'


def _full_name(user) -> str:
    if user is None:
        return ''
    return f"{user.first_name} {user.last_name} {user.mother_last_name or ''}".strip()


def _as_datetime(value):
    """`granted_until` column is a DateTime: a bare date means end of that day."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time(23, 59, 59))
    return None


class ExtensionKind(ReviewKind):
    key = 'extension'
    label = 'Prórroga'
    permission = 'extensions.api.decide'
    model = ExtensionRequest
    pending_statuses = ('pending',)
    decided_statuses = ('granted', 'rejected')
    status_by_decision = {'approve': 'granted', 'reject': 'rejected'}
    not_found_message = 'Solicitud de prórroga no encontrada.'

    # ── Loading ──────────────────────────────────────────────────────────

    def load_for_update(self, item_uuid):
        row = ExtensionRequest.by_uuid(item_uuid)
        if row is None:
            return None
        return (ExtensionRequest.query.filter_by(id=row.id)
                .with_for_update().populate_existing().first())

    # ── Ownership ────────────────────────────────────────────────────────

    def program_id(self, item) -> Optional[int]:
        if item is None:
            return None
        if item.user_program_id is not None:
            up = db.session.get(UserProgram, item.user_program_id)
            if up is not None:
                return up.program_id
        if item.program_step is not None:
            return item.program_step.program_id
        return None

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
        if item.status == 'cancelled':
            raise ReviewConflict(CANCELLED_MESSAGE)
        granted_until = None
        if status == 'granted':
            granted_until = _as_datetime(extra.get('granted_until'))
            if granted_until is None:
                raise ReviewConflict(GRANTED_UNTIL_REQUIRED_MESSAGE)
        now = self.now()
        item.status = status
        item.decided_by = actor.id
        item.decided_at = now
        item.updated_at = now
        item.granted_until = granted_until
        item.condition_text = extra.get('condition_text')

    # ── After the commit ─────────────────────────────────────────────────

    def log_decision(self, item, status, actor, comment) -> None:
        # Also sends the student's notice (granted / rejected).
        formatted = None
        if status == 'granted' and item.granted_until:
            formatted = item.granted_until.strftime('%d/%m/%Y')
        UserHistoryService.log_extension_decision(
            user_id=item.user_id,
            archive_name=self.title(item),
            decision=status,
            granted_until=formatted,
            condition_text=item.condition_text,
            admin_id=actor.id,
        )

    def notify(self, item, status, reverted) -> None:
        # A first decision is announced by `log_decision`; only a change is here.
        if not reverted:
            return
        if status == 'granted':
            formatted = item.granted_until.strftime('%d/%m/%Y') if item.granted_until else None
            NotificationService.notify_extension_approved(
                item.user_id, self.title(item), formatted)
        else:
            NotificationService.notify_extension_rejected(
                item.user_id, self.title(item), item.condition_text)

    def emit(self, item, status, reverted) -> None:
        from app.sockets.emitters import emit_user_and_coordinators

        program_id = self.program_id(item)
        emit_user_and_coordinators(
            'extension:decided',
            {
                'user_id': public_id_service.user_uuid(item.user_id),
                'extension_request_id': item.id,
                'archive_id': public_id_service.archive_uuid(item.archive_id),
                'program_id': program_id,
                'status': status,
                'granted_until': item.granted_until.isoformat() if item.granted_until else None,
            },
            user_id=item.user_id,
            program_id=program_id,
        )

    # ── Inbox ────────────────────────────────────────────────────────────

    def _base_query(self, program_ids):
        q = (ExtensionRequest.query
             .join(ProgramStep, ExtensionRequest.program_step_id == ProgramStep.id)
             .outerjoin(UserProgram, ExtensionRequest.user_program_id == UserProgram.id))
        if program_ids is not None:
            q = q.filter(func.coalesce(UserProgram.program_id, ProgramStep.program_id)
                         .in_(program_ids))
        return q

    def pending_query(self, program_ids):
        return (self._base_query(program_ids)
                .filter(ExtensionRequest.status.in_(self.pending_statuses))
                .order_by(ExtensionRequest.created_at.asc(), ExtensionRequest.id.asc()))

    def decided_query(self, program_ids, since: datetime):
        return (self._base_query(program_ids)
                .filter(ExtensionRequest.status.in_(self.decided_statuses),
                        ExtensionRequest.decided_at.isnot(None),
                        ExtensionRequest.decided_at >= since)
                .order_by(ExtensionRequest.decided_at.desc(), ExtensionRequest.id.desc()))

    def title(self, item) -> str:
        if item.archive is not None:
            return item.archive.name
        return f'Documento ID {item.archive_id}'

    def submitted_at(self, item):
        return item.created_at

    def decided_at(self, item):
        return item.decided_at

    def row(self, item) -> dict:
        program_id = self.program_id(item)
        program = db.session.get(Program, program_id) if program_id else None
        return {
            'uuid': str(item.uuid),
            'kind': self.key,
            'kind_label': self.label,
            'student_name': _full_name(item.user),
            'student_uuid': public_id_service.user_uuid(item.user_id),
            'program_id': program.id if program else None,
            'program_name': program.name if program else None,
            'title': self.title(item),
            'uploaded_at': self.submitted_at(item),
            'file_url': None,
            'status': item.status,
            'decided_at': self.decided_at(item),
            'comment': item.condition_text,
        }


register(ExtensionKind())

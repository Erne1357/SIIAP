"""
`decide()` — the single entry point that approves, rejects or changes a
decision on any reviewable item (phase 6D).

Rules, in order:
1. the kind exists (404) and the decision is approve/reject (400);
2. the actor holds the kind's decision permission (403);
3. the item exists, belongs to the kind and its program is in the actor's
   scope (404 — unknown and out of scope are indistinguishable); it is
   loaded row-locked;
4. pending -> decide. Already decided -> a non-empty `revert_reason` is
   required and the target status must differ from the current one
   (409 otherwise, nothing written);
5. reverting an approval: refused when the student program is `titled`
   (409); otherwise the kind undoes its automatic effects (`on_reverted`);
6. `apply` (+ `on_approved` when approving) and commit;
7. after the commit, best effort: history (`document_review_reverted` for a
   change of decision, with `user_program_id`), notice + e-mail, the kind's
   legacy socket event and `review:decided`.

Framework-agnostic: the caller passes the acting `User`.
"""
from __future__ import annotations

import logging
from typing import Optional

from app import db
from app.models.user_program import UserProgram
from app.services import program_scope_service as scope_service
from app.services.review_engine.base import VALID_DECISIONS, Decision, ReviewKind
from app.services.review_engine.errors import (
    ReviewConflict, ReviewError, ReviewForbidden, ReviewNotFound,
)
from app.services.review_engine.registry import get_kind
from app.services.user_history_service import UserHistoryService

logger = logging.getLogger(__name__)

TITLED_STATUS = 'titled'

INVALID_DECISION_MESSAGE = 'Decisión inválida.'
FORBIDDEN_MESSAGE = 'No tienes permiso para decidir este tipo de revisión.'
REASON_REQUIRED_MESSAGE = 'Ya fue decidido; para cambiarlo indica el motivo.'
SAME_DECISION_MESSAGE = 'Esa ya es la decisión vigente; no hay nada que cambiar.'
TITLED_MESSAGE = 'El estudiante ya está titulado; la aprobación no se puede revertir.'


def _normalize_decision(decision) -> str:
    decision = (decision or '').strip().lower() if isinstance(decision, str) else ''
    if decision not in VALID_DECISIONS:
        raise ReviewError(INVALID_DECISION_MESSAGE)
    return decision


def _resolve_kind(kind) -> ReviewKind:
    return kind if isinstance(kind, ReviewKind) else get_kind(kind)


def decide(actor, kind: str, item_uuid, decision: str, comment: str = '',
           revert_reason: Optional[str] = None, extra: Optional[dict] = None) -> Decision:
    """
    Decide on the item `item_uuid` of `kind` as `actor`. Commits.

    Raises ReviewNotFound (404), ReviewForbidden (403), ReviewConflict (409)
    or ReviewError (400); nothing is written when it raises.
    """
    kind_obj = _resolve_kind(kind)
    decision = _normalize_decision(decision)
    if actor is None or not actor.has_permission(kind_obj.permission):
        raise ReviewForbidden(FORBIDDEN_MESSAGE)
    item = kind_obj.load_for_update(item_uuid)
    return decide_item(actor, kind_obj, item, decision, comment=comment,
                       revert_reason=revert_reason, extra=extra)


def decide_item(actor, kind, item, decision: str, comment: str = '',
                revert_reason: Optional[str] = None, extra: Optional[dict] = None) -> Decision:
    """
    Same rules as `decide` from step 3 on, for an item the caller already
    loaded (and locked). It does NOT check the kind's permission: it serves
    the legacy services whose routes enforce their own codename. Commits.
    """
    kind_obj = _resolve_kind(kind)
    decision = _normalize_decision(decision)
    if item is None or not scope_service.program_in_scope(actor, kind_obj.program_id(item)):
        raise ReviewNotFound(kind_obj.not_found_message)

    previous = kind_obj.status(item)
    target = kind_obj.status_for(decision)
    reverted = not kind_obj.is_pending(item)
    reason = (revert_reason or '').strip()
    comment = (comment or '').strip()
    if reverted:
        if not reason:
            raise ReviewConflict(REASON_REQUIRED_MESSAGE)
        if target == previous:
            raise ReviewConflict(SAME_DECISION_MESSAGE)
        comment = comment or reason

    approved_status = kind_obj.status_for('approve')
    try:
        if reverted and previous == approved_status:
            up_id = kind_obj.user_program_id(item)
            # Locked so a titling committed at the same moment is seen.
            up = (UserProgram.query.filter_by(id=up_id).with_for_update()
                  .populate_existing().first() if up_id else None)
            if up is not None and up.academic_status == TITLED_STATUS:
                raise ReviewConflict(TITLED_MESSAGE)
            kind_obj.on_reverted(item, actor)
        kind_obj.apply(item, target, actor, comment, dict(extra or {}))
        if decision == 'approve':
            kind_obj.on_approved(item, actor)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    result = Decision(item=item, kind=kind_obj, status=target, reverted=reverted,
                      previous_status=previous)
    _after_commit(actor, kind_obj, item, target, previous, reverted, comment, reason)
    return result


def _after_commit(actor, kind: ReviewKind, item, status: str, previous: str,
                  reverted: bool, comment: str, reason: str) -> None:
    try:
        if reverted:
            student = kind.student(item)
            UserHistoryService.log_action(
                user_id=student.id, admin_id=actor.id, action='document_review_reverted',
                user_program_id=kind.user_program_id(item),
                details={'kind': kind.key, 'item_id': str(getattr(item, 'uuid', '') or ''),
                         'title': kind.title(item), 'from': previous, 'to': status,
                         'reason': reason},
            )
        else:
            kind.log_decision(item, status, actor, comment)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error('review_engine: history of %s failed: %s', kind.key, exc)

    try:
        kind.notify(item, status, reverted)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error('review_engine: notice of %s failed: %s', kind.key, exc)

    try:
        kind.emit(item, status, reverted)
    except Exception as exc:
        logger.warning('review_engine: socket of %s failed: %s', kind.key, exc)

    try:
        from app.services import public_id_service
        from app.sockets.emitters import emit_user_and_coordinators

        student = kind.student(item)
        program_id = kind.program_id(item)
        emit_user_and_coordinators(
            'review:decided',
            {
                'kind': kind.key,
                'item_id': str(getattr(item, 'uuid', '') or ''),
                'user_id': public_id_service.user_uuid(student.id),
                'program_id': program_id,
                'status': status,
                'reverted': reverted,
            },
            user_id=student.id,
            program_id=program_id,
        )
    except Exception as exc:
        logger.warning('review_engine: review:decided emit failed: %s', exc)

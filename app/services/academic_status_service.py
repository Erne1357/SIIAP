"""
Single source of truth for `UserProgram.academic_status` transitions.

`admission_status` ends at `enrolled`; from then on the student's trajectory
is tracked here, so admission and trajectory never mix:

    NULL ──► active ◄──► on_leave
               │  ╲          │
               │   ╲         ▼
               │    ──► withdrawn ──(admin revert)──► active
               ▼
           graduated ──► titled ──(admin revert)──► graduated

Business rules fixed by the owner (2026-10-21):
- The coordinator registers graduation explicitly, with a date.
- A definitive withdrawal needs a reason and is terminal; only a
  `postgraduate_admin` reverts it (`allow_revert=True`), with a reason.
- Phase 6C: an approved grade exam titles the student (`titled`, with
  `titled_at`). It is terminal too; reverting it to `graduated` follows the
  same rule as a withdrawal (admin, `allow_revert=True`, reason).

Unlike `admission_status_service`, this module writes the history entry
itself: every caller logs the same action. It never commits.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from app.models.user_program import UserProgram
from app.services.errors import DomainError
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local

ACTIVE = 'active'
ON_LEAVE = 'on_leave'
WITHDRAWN = 'withdrawn'
GRADUATED = 'graduated'
TITLED = 'titled'

#: Every value the `ck_user_program_academic_status` CHECK accepts.
ALL_STATUSES = frozenset({ACTIVE, ON_LEAVE, WITHDRAWN, GRADUATED, TITLED})

#: Trajectory finished: no further semester enrollment.
CLOSED_STATUSES = frozenset({WITHDRAWN, GRADUATED, TITLED})

#: Terminal statuses only a `postgraduate_admin` reverts (from -> to).
REVERTS = {WITHDRAWN: ACTIVE, TITLED: GRADUATED}

#: Students who may still enroll in a semester.
CURRENT_STATUSES = frozenset({ACTIVE, ON_LEAVE})

#: from-status -> statuses it may move to. `None` is a program not yet enrolled.
ALLOWED_TRANSITIONS: dict[Optional[str], frozenset[str]] = {
    None: frozenset({ACTIVE}),
    ACTIVE: frozenset({ON_LEAVE, WITHDRAWN, GRADUATED}),
    ON_LEAVE: frozenset({ACTIVE, WITHDRAWN}),
    WITHDRAWN: frozenset({ACTIVE}),
    GRADUATED: frozenset({TITLED}),
    TITLED: frozenset({GRADUATED}),
}

STATUS_LABELS_ES = {
    None: 'sin inscripción',
    ACTIVE: 'activo',
    ON_LEAVE: 'baja temporal',
    WITHDRAWN: 'baja definitiva',
    GRADUATED: 'egresado',
    TITLED: 'titulado',
}


class InvalidAcademicTransition(DomainError):
    """The requested trajectory change is not allowed from the current status."""

    def __init__(self, from_status: Optional[str], to_status: str):
        super().__init__(
            f'No se puede cambiar el estado académico de '
            f'"{STATUS_LABELS_ES.get(from_status, from_status)}" a '
            f'"{STATUS_LABELS_ES.get(to_status, to_status)}".'
        )
        self.from_status = from_status
        self.to_status = to_status


def can_transition(from_status: Optional[str], to_status: str) -> bool:
    """True if `from_status` may move to `to_status` (revert rules aside)."""
    return (to_status in ALL_STATUSES
            and to_status in ALLOWED_TRANSITIONS.get(from_status, frozenset()))


def transition(user_program: UserProgram, to_status: str, *, actor_id: Optional[int],
               reason: Optional[str] = None, on_date: Optional[date] = None,
               allow_revert: bool = False) -> Optional[str]:
    """
    Move `user_program` to `to_status`, stamp its dates and log the change.

    Raises InvalidAcademicTransition for a move outside the map (or a revert
    without `allow_revert`) and DomainError for a missing reason or date.
    Returns the previous status. Does not commit.
    """
    from_status = user_program.academic_status
    if (from_status is None and to_status != ACTIVE
            and user_program.admission_status == 'enrolled'):
        # Enrolled by the previous color during a blue-green switch (it does
        # not know this column) or before the backfill: an active student.
        from_status = ACTIVE
    if not can_transition(from_status, to_status):
        raise InvalidAcademicTransition(from_status, to_status)

    reason = (reason or '').strip() or None
    reverting = from_status in REVERTS
    if reverting and not allow_revert:
        raise InvalidAcademicTransition(from_status, to_status)
    if (reverting or to_status == WITHDRAWN) and not reason:
        raise DomainError('El motivo es obligatorio.')
    if to_status == GRADUATED and on_date is None and not reverting:
        raise DomainError('La fecha de egreso es obligatoria.')
    if to_status == TITLED and on_date is None:
        raise DomainError('La fecha del examen de grado es obligatoria.')

    now = now_local()
    user_program.academic_status = to_status
    user_program.academic_status_changed_at = now
    if to_status == WITHDRAWN:
        user_program.withdrawn_at = now
        user_program.withdrawal_reason = reason
    elif to_status == GRADUATED and not reverting:
        user_program.graduated_at = on_date
    elif to_status == TITLED:
        user_program.titled_at = on_date
    if from_status == TITLED:
        user_program.titled_at = None

    details = {
        'program_id': user_program.program_id,
        'from': from_status,
        'to': to_status,
    }
    if reason:
        details['reason'] = reason
    if on_date is not None:
        details['date'] = on_date.isoformat()
    UserHistoryService.log_action(
        user_id=user_program.user_id,
        action='academic_status_changed',
        details=details,
        admin_id=actor_id,
        user_program_id=user_program.id,
    )
    return from_status

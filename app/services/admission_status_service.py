"""
Single source of truth for `UserProgram.admission_status` transitions.

Before this module, 18 call sites in 12 files assigned the status directly,
each with its own (or no) guard. That allowed, among others:

- a forced reset of an `enrolled` student back to `in_progress` while they
  kept the student role, control number and semester enrollments;
- the semester transition overwriting a committee's `rejected` decision
  with `expired`;
- two deferral reactivation paths ending in different states.

Every write now goes through `transition()`, which checks the move against
`ALLOWED_TRANSITIONS`. History, notifications and socket events stay with the
caller: each flow logs its own action name and details.

Business rules fixed by the owner (2026-10-19):
- `enrolled` is terminal: no reset, no expiry.
- Expiry applies to applicants still in process and to `accepted` applicants
  who never enrolled; `rejected` keeps the committee's decision.
- A deferred applicant comes back `accepted`, whichever path reactivates it.
- Summer periods (code ending in 2) do not count when measuring how many
  periods an applicant has been waiting.
"""
from __future__ import annotations

from typing import Iterable, Optional

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.user_program import UserProgram

IN_PROGRESS = 'in_progress'
INTERVIEW_COMPLETED = 'interview_completed'
DELIBERATION = 'deliberation'
ACCEPTED = 'accepted'
REJECTED = 'rejected'
DEFERRED = 'deferred'
ENROLLED = 'enrolled'
EXPIRED = 'expired'

#: Every value the `ck_user_program_admission_status` CHECK accepts.
ALL_STATUSES = frozenset({
    IN_PROGRESS, INTERVIEW_COMPLETED, DELIBERATION, ACCEPTED,
    REJECTED, DEFERRED, ENROLLED, EXPIRED,
})

#: Applicants whose admission process is still open.
IN_PROCESS_STATUSES = frozenset({IN_PROGRESS, INTERVIEW_COMPLETED, DELIBERATION})

#: Who the period-based expiry may move to `expired`.
EXPIRABLE_STATUSES = IN_PROCESS_STATUSES | {ACCEPTED}

#: from-status -> statuses it may move to. A self-loop is listed only where a
#: flow really rewrites the same status (program transfer keeps `in_progress`).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    IN_PROGRESS: frozenset({IN_PROGRESS, INTERVIEW_COMPLETED, EXPIRED}),
    INTERVIEW_COMPLETED: frozenset({DELIBERATION, ACCEPTED, REJECTED, EXPIRED, IN_PROGRESS}),
    DELIBERATION: frozenset({ACCEPTED, REJECTED, EXPIRED, IN_PROGRESS}),
    ACCEPTED: frozenset({DEFERRED, ENROLLED, EXPIRED, IN_PROGRESS}),
    REJECTED: frozenset({IN_PROGRESS}),
    DEFERRED: frozenset({ACCEPTED, EXPIRED, IN_PROGRESS}),
    EXPIRED: frozenset({IN_PROGRESS}),
    ENROLLED: frozenset(),
}

#: Targets the administrative override (`override=True`) may force from any
#: non-terminal status: registering a student who never went through the
#: online admission (legacy or bulk enrollment).
OVERRIDE_TARGETS = frozenset({ENROLLED})

_STATUS_LABELS_ES = {
    IN_PROGRESS: 'en proceso',
    INTERVIEW_COMPLETED: 'entrevista completada',
    DELIBERATION: 'en deliberación',
    ACCEPTED: 'aceptado',
    REJECTED: 'rechazado',
    DEFERRED: 'diferido',
    ENROLLED: 'inscrito',
    EXPIRED: 'expirado',
}


class InvalidAdmissionTransition(Exception):
    """The requested status change is not allowed from the current status."""

    def __init__(self, from_status: str, to_status: str):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f'No se puede cambiar el estado de admisión de '
            f'"{_STATUS_LABELS_ES.get(from_status, from_status)}" a '
            f'"{_STATUS_LABELS_ES.get(to_status, to_status)}".'
        )


def can_transition(from_status: str, to_status: str, *, override: bool = False) -> bool:
    """True if `from_status` may move to `to_status`."""
    if to_status not in ALL_STATUSES:
        return False
    if override and to_status in OVERRIDE_TARGETS:
        return from_status != ENROLLED
    return to_status in ALLOWED_TRANSITIONS.get(from_status, frozenset())


def transition(user_program: UserProgram, to_status: str, *, override: bool = False) -> str:
    """
    Move `user_program` to `to_status` or raise InvalidAdmissionTransition.

    Returns the previous status. Does not commit: the caller owns the
    transaction, history entry, notification and socket event.
    """
    from_status = user_program.admission_status
    if not can_transition(from_status, to_status, override=override):
        raise InvalidAdmissionTransition(from_status, to_status)
    user_program.admission_status = to_status
    return from_status


def lock_user_program(user_id: int, program_id: int) -> Optional[UserProgram]:
    """
    Load the UserProgram row with `SELECT ... FOR UPDATE`.

    Two coordinators deciding on the same applicant used to both pass the
    same check-then-set guard. The lock serialises them until the caller's
    commit; SQLite (tests) ignores it.
    """
    return (
        UserProgram.query
        .filter_by(user_id=user_id, program_id=program_id)
        .with_for_update()
        .first()
    )


# ── Period distance ──────────────────────────────────────────────────────────

def is_summer_period(period: AcademicPeriod) -> bool:
    """Summer periods have codes ending in 2 (YYYY2)."""
    return bool(period.code) and period.code.endswith('2')


def regular_period_ids() -> list[int]:
    """Ids of non-summer periods in chronological order (by start_date)."""
    rows = (
        db.session.query(AcademicPeriod.id, AcademicPeriod.code)
        .order_by(AcademicPeriod.start_date, AcademicPeriod.id)
        .all()
    )
    return [pid for pid, code in rows if not (code or '').endswith('2')]


def _next_regular_period(period: AcademicPeriod) -> Optional[AcademicPeriod]:
    """First non-summer period starting after `period` (None if none exists)."""
    later = (
        AcademicPeriod.query
        .filter(AcademicPeriod.start_date > period.start_date)
        .order_by(AcademicPeriod.start_date, AcademicPeriod.id)
        .all()
    )
    return next((p for p in later if not is_summer_period(p)), None)


def regular_periods_between(from_period_id: Optional[int], to_period_id: Optional[int],
                            ordered_ids: Optional[Iterable[int]] = None) -> Optional[int]:
    """
    Non-summer periods from `from_period_id` to `to_period_id` (to - from).

    A summer starting period is anchored to the next regular period, so an
    applicant admitted in summer is measured like one admitted in the
    following semester instead of never expiring. A summer target returns
    None: applicants never move into a summer period. Missing ids -> None.
    """
    if from_period_id is None or to_period_id is None:
        return None
    ids = list(ordered_ids) if ordered_ids is not None else regular_period_ids()
    if from_period_id not in ids:
        start = db.session.get(AcademicPeriod, from_period_id)
        anchor = _next_regular_period(start) if start is not None and is_summer_period(start) else None
        if anchor is None:
            return None
        from_period_id = anchor.id
    try:
        return ids.index(to_period_id) - ids.index(from_period_id)
    except ValueError:
        return None


def regular_periods_closed_since(period: AcademicPeriod, today) -> int:
    """
    Non-summer periods after `period` whose admission window closed before
    `today`. Used by the purge and cleanup flows, which run on a date rather
    than on a period transition. A summer `period` is anchored to the next
    regular one, exactly as in `regular_periods_between`.
    """
    if is_summer_period(period):
        anchor = _next_regular_period(period)
        if anchor is None:
            return 0
        period = anchor
    later = (
        AcademicPeriod.query
        .filter(
            AcademicPeriod.start_date > period.start_date,
            AcademicPeriod.admission_end_date < today,
        )
        .all()
    )
    return sum(1 for p in later if not is_summer_period(p))

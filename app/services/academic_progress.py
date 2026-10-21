# app/services/academic_progress.py
"""
Academic semester and permanence limit of an enrolled student.

Two counters that used to be one (`max(semester_number) + 1`):

- **Academic semester** advances only with a semester actually studied:
  highest completed semester + 1. A student back from a temporary leave repeats
  the semester they left, instead of skipping one.
- **Permanence limit** is measured in calendar periods: regular (non-summer)
  periods from the first period the student enrolled in up to the target,
  both included, at most `duration_semesters + 4`. A temporary leave does
  consume a period (owner's decision, 2026-10-21); summer never does.

Shared by `permanence_service` and `semester_transition_service`.
"""
from __future__ import annotations

from typing import Optional

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.semester_enrollment import SemesterEnrollment
from app.models.user_program import UserProgram
from app.services.admission_status_service import regular_periods_between
from app.services.errors import DomainError

#: Extra regular periods allowed beyond the plan length.
GRACE_PERIODS = 4

#: SemesterEnrollment.status -> statuses it may move to. `dropped` is reached
#: only through `permanence_service.withdraw()`.
SE_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    'pending': frozenset({'active', 'dropped'}),
    'active': frozenset({'completed', 'on_leave', 'dropped'}),
    'on_leave': frozenset({'active', 'dropped'}),
    'completed': frozenset(),
    'dropped': frozenset(),
}

SE_STATUS_LABELS_ES = {
    'pending': 'Pendiente',
    'active': 'Activo',
    'completed': 'Completado',
    'on_leave': 'Baja temporal',
    'dropped': 'Baja definitiva',
}


class PermanenceLimitExceeded(DomainError):
    """Enrolling in the target period would pass `duration_semesters + 4`."""


def can_change_enrollment_status(from_status: str, to_status: str) -> bool:
    return to_status in SE_ALLOWED_TRANSITIONS.get(from_status, frozenset())


def chronological_enrollments(user_program_id: int):
    return (
        SemesterEnrollment.query
        .outerjoin(AcademicPeriod, AcademicPeriod.id == SemesterEnrollment.academic_period_id)
        .filter(SemesterEnrollment.user_program_id == user_program_id)
    )


def last_enrollment(user_program_id: int) -> Optional[SemesterEnrollment]:
    """Most recent enrollment by period start (semester numbers may repeat)."""
    return (
        chronological_enrollments(user_program_id)
        .order_by(AcademicPeriod.start_date.desc(), SemesterEnrollment.id.desc())
        .first()
    )


def first_enrollment(user_program_id: int) -> Optional[SemesterEnrollment]:
    return (
        chronological_enrollments(user_program_id)
        .order_by(AcademicPeriod.start_date.asc(), SemesterEnrollment.id.asc())
        .first()
    )


def completed_semesters(user_program_id: int) -> int:
    """Highest semester the student finished (0 if none)."""
    return (
        db.session.query(db.func.max(SemesterEnrollment.semester_number))
        .filter_by(user_program_id=user_program_id, status='completed')
        .scalar()
    ) or 0


def next_semester_number(user_program_id: int, *,
                         closing: Optional[SemesterEnrollment] = None) -> int:
    """
    Academic semester of the next enrollment: highest completed semester + 1.

    Imported students may have no rows for their early semesters, so the
    rule reads semester numbers instead of counting rows. With nothing
    completed, the earliest recorded semester is repeated (a student whose
    only row is a leave resumes that semester); with no rows at all, 1.

    `closing` is an enrollment the caller is about to mark completed but has
    not yet (transition preview); it counts as completed.
    """
    done = completed_semesters(user_program_id)
    if closing is not None and closing.status in ('active', 'pending'):
        done = max(done, closing.semester_number or 0)
    if done:
        return done + 1
    earliest = (
        db.session.query(db.func.min(SemesterEnrollment.semester_number))
        .filter_by(user_program_id=user_program_id)
        .scalar()
    )
    return earliest or 1


def regular_periods_elapsed(user_program_id: int, target_period_id: int) -> Optional[int]:
    """
    Regular periods from the first enrolled period to `target_period_id`,
    both included. None when it cannot be measured (no enrollment yet, or a
    summer target, which never counts).
    """
    first = first_enrollment(user_program_id)
    if first is None:
        return 1
    distance = regular_periods_between(first.academic_period_id, target_period_id)
    return None if distance is None else distance + 1


def permanence_limit(user_program: UserProgram) -> Optional[int]:
    duration = user_program.program.duration_semesters if user_program.program else None
    return duration + GRACE_PERIODS if duration else None


def limit_exceeded_message(user_program: UserProgram, target_period_id: int) -> Optional[str]:
    """Spanish reason why enrolling in `target_period_id` passes the limit, or None."""
    limit = permanence_limit(user_program)
    if limit is None:
        return None
    elapsed = regular_periods_elapsed(user_program.id, target_period_id)
    if elapsed is None or elapsed <= limit:
        return None
    duration = user_program.program.duration_semesters
    return (
        f'Excede el límite de permanencia del programa: serían {elapsed} periodos '
        f'desde su primera inscripción (máximo {limit}: duración {duration} + '
        f'{GRACE_PERIODS}; las bajas temporales cuentan, el verano no).'
    )


def assert_within_permanence_limit(user_program: UserProgram, target_period_id: int) -> None:
    message = limit_exceeded_message(user_program, target_period_id)
    if message:
        raise PermanenceLimitExceeded(message)

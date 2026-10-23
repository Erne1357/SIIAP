# app/services/course_load_service.py
"""
Read helpers for the "Carga académica" screens (phase 6B1): what to show for a
program and period, who can still be enrolled in a group, who is a candidate
for a semester enrollment. Rules live in `course_group_service` and
`course_enrollment_service`; nothing here writes.
"""
from __future__ import annotations

from typing import Optional

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.course_enrollment import ATTEMPT_TYPES, MAX_ATTEMPTS, CourseEnrollment
from app.models.course_group import CourseGroup
from app.models.program import Program
from app.models.user_program import UserProgram
from app.services import (
    academic_period_service, academic_status_service, course_enrollment_service,
    course_group_service, curriculum_service, teacher_service,
)

ATTEMPT_LABELS = {'ordinary': 'Ordinario', 'repeat': 'Repetición', 'special': 'Especial'}
#: attempt type -> `.status-badge--*` modifier
ATTEMPT_BADGES = {'ordinary': 'accepted', 'repeat': 'deferred', 'special': 'review'}


def get_program(program_id: int) -> Optional[Program]:
    return db.session.get(Program, program_id)


def resolve_period(raw) -> Optional[AcademicPeriod]:
    """The period asked for, else the active one, else the newest."""
    try:
        period = db.session.get(AcademicPeriod, int(raw)) if raw not in (None, '') else None
    except (TypeError, ValueError):
        period = None
    if period is None:
        period = academic_period_service.get_active_period()
    if period is None:
        periods = academic_period_service.list_periods_newest_first()
        period = periods[0] if periods else None
    return period


def _full_name(user) -> str:
    return (f'{user.last_name} {user.mother_last_name or ""} {user.first_name}'
            .replace('  ', ' ').strip())


def _active_students(program_id: int) -> list[UserProgram]:
    rows = (UserProgram.query
            .filter(UserProgram.program_id == program_id,
                    UserProgram.admission_status == 'enrolled',
                    db.or_(UserProgram.academic_status == academic_status_service.ACTIVE,
                           UserProgram.academic_status.is_(None)))
            .all())
    return sorted(rows, key=lambda up: _full_name(up.user).lower())


def offerable_subjects(program_id: int, include_subject_id: Optional[int] = None) -> list[dict]:
    """Subjects a group may be created for: the current plan's, plus the group's own when editing."""
    plan = curriculum_service.current_plan(program_id)
    subjects = [s for s in (curriculum_service.subjects_of(plan.id) if plan else [])
                if s.kind != 'elective_slot']
    if include_subject_id and all(s.id != include_subject_id for s in subjects):
        subjects.append(curriculum_service.get_subject(include_subject_id))
    return [{'id': s.id, 'label': f'{s.key + " · " if s.key else ""}{s.name}'} for s in subjects]


def program_view(program: Program, period_raw=None) -> dict:
    """Context of the groups-of-a-period fragment."""
    period = resolve_period(period_raw)
    groups = course_group_service.groups_for(program.id, period.id) if period else []
    return {
        'program': program,
        'period': period,
        'periods': academic_period_service.list_periods_newest_first(),
        'groups': groups,
        'subjects': offerable_subjects(program.id),
        'teachers': teacher_service.teacher_choices(),
        'students': semester_candidates(program.id),
        'summary': None,
    }


def semester_candidates(program_id: int) -> list[dict]:
    return [{'id': up.id, 'name': _full_name(up.user), 'control_number': up.user.control_number,
             'semester': up.current_semester or 1} for up in _active_students(program_id)]


def candidates_for(group: CourseGroup) -> list[dict]:
    """Active students of the group's program who may still be enrolled in it."""
    taken = {uid for (uid,) in db.session.query(CourseEnrollment.user_program_id).filter(
        CourseEnrollment.subject_id == group.subject_id,
        CourseEnrollment.academic_period_id == group.academic_period_id,
        CourseEnrollment.status != 'dropped')}
    out = []
    for up in _active_students(group.program_id):
        if up.id in taken or up.curriculum_plan_id != group.subject.plan_id:
            continue
        attempt = course_enrollment_service.next_attempt(up.id, group.subject_id)
        if attempt > MAX_ATTEMPTS:
            continue
        out.append({'id': up.id, 'name': _full_name(up.user),
                    'control_number': up.user.control_number,
                    'attempt_label': ATTEMPT_LABELS[ATTEMPT_TYPES[attempt]]})
    return out


def group_view(group: CourseGroup) -> dict:
    """Context of the group-detail fragment."""
    roster = course_group_service.roster(group.id)
    for row in roster:
        row['attempt_label'] = ATTEMPT_LABELS.get(row['attempt_type'], row['attempt_type'])
        row['attempt_badge'] = ATTEMPT_BADGES.get(row['attempt_type'], 'pending')
    slots = []
    if group.subject.kind == 'elective':
        slots = [s for s in curriculum_service.subjects_of(group.subject.plan_id)
                 if s.kind == 'elective_slot']
    return {
        'group': group,
        'program': group.program,
        'period': group.academic_period,
        'periods': academic_period_service.list_periods_newest_first(),
        'roster': roster,
        'enrolled': len(roster),
        'full': len(roster) >= group.capacity,
        'candidates': candidates_for(group),
        'slots': slots,
        'subjects': offerable_subjects(group.program_id, group.subject_id),
        'teachers': teacher_service.teacher_choices(),
        'teacher_name': (f'{group.teacher.first_name} {group.teacher.last_name}'.strip()
                         if group.teacher else None),
    }


def enrollment_of_group(group_id: int, enrollment_id: int) -> Optional[CourseEnrollment]:
    """The active enrollment, only if it belongs to the group (no cross-group drops)."""
    return CourseEnrollment.query.filter_by(
        id=enrollment_id, course_group_id=group_id, status='enrolled').first()


def groups_of_program(program_id: int, group_ids: list[int]) -> list[int]:
    """Subset of `group_ids` that are groups of the program (ids from a form are not trusted)."""
    if not group_ids:
        return []
    rows = db.session.query(CourseGroup.id).filter(
        CourseGroup.program_id == program_id, CourseGroup.id.in_(group_ids)).all()
    return [gid for (gid,) in rows]


def students_of_program(program_id: int, user_program_ids: list[int]) -> list[int]:
    """Subset of `user_program_ids` that are student links of the program."""
    if not user_program_ids:
        return []
    rows = db.session.query(UserProgram.id).filter(
        UserProgram.program_id == program_id, UserProgram.id.in_(user_program_ids)).all()
    return [uid for (uid,) in rows]

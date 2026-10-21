# app/services/course_enrollment_service.py
"""
Enrolling students into course groups — the academic load (phase 6B1).

One `CourseEnrollment` row per attempt: 1st ordinary, 2nd repeat, 3rd
special (TecNM's SII). A dropped row is kept and does not count. Phase 6B2
grades these rows and rejects enrolling in a passed subject.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app import db
from app.models.course_enrollment import ATTEMPT_TYPES, MAX_ATTEMPTS, CourseEnrollment
from app.models.course_group import CourseGroup
from app.models.user_program import UserProgram
from app.services import academic_status_service, course_group_service, curriculum_service
from app.services.errors import DomainError, NotFoundError
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local


class EnrollmentRuleError(DomainError):
    """Business rule of the academic load."""


def next_attempt(user_program_id: int, subject_id: int) -> int:
    taken = (db.session.query(db.func.count(CourseEnrollment.id))
             .filter(CourseEnrollment.user_program_id == user_program_id,
                     CourseEnrollment.subject_id == subject_id,
                     CourseEnrollment.status != 'dropped')
             .scalar()) or 0
    return taken + 1


def _lock_student(user_program_id: int) -> Optional[UserProgram]:
    """Row lock on the student program: serialises two enrollments of one student."""
    return (UserProgram.query.filter_by(id=user_program_id)
            .with_for_update().populate_existing().first())


def _check_student(up: Optional[UserProgram], group: CourseGroup) -> UserProgram:
    if up is None or up.program_id != group.program_id:
        # Same answer as an unknown id: a student of another program is not ours to know.
        raise NotFoundError('Estudiante no encontrado.')
    if up.admission_status != 'enrolled' or up.academic_status not in (
            academic_status_service.ACTIVE, None):
        label = academic_status_service.STATUS_LABELS_ES.get(up.academic_status,
                                                             up.academic_status)
        raise EnrollmentRuleError(
            f'Sólo se inscriben estudiantes activos (estado académico: {label}).')
    return up


def _check_subject(up: UserProgram, group: CourseGroup,
                   slot_subject_id: Optional[int]) -> Optional[int]:
    subject = group.subject
    if up.curriculum_plan_id != subject.plan_id:
        raise EnrollmentRuleError('La materia no pertenece a la versión del plan del estudiante.')
    if subject.kind != 'elective':
        return None
    # Repeating an elective keeps the slot of the earlier attempt.
    earlier = (CourseEnrollment.query
               .filter(CourseEnrollment.user_program_id == up.id,
                       CourseEnrollment.subject_id == subject.id,
                       CourseEnrollment.status != 'dropped',
                       CourseEnrollment.academic_period_id != group.academic_period_id,
                       CourseEnrollment.slot_subject_id.isnot(None))
               .first())
    if earlier is not None:
        return earlier.slot_subject_id
    open_ids = {s.id for s in curriculum_service.open_slots(up)}
    if slot_subject_id is None:
        if not open_ids:
            raise EnrollmentRuleError('El estudiante ya cubrió todas sus optativas.')
        slot_subject_id = min(open_ids)
    elif slot_subject_id not in open_ids:
        raise EnrollmentRuleError('Ese hueco de optativa ya está cubierto o no es de su plan.')
    return slot_subject_id


def enroll(group_id: int, user_program_id: int, actor_id: int, *,
           slot_subject_id: Optional[int] = None) -> CourseEnrollment:
    """Enroll a student in a group; locks the group so capacity holds under double submits."""
    group = course_group_service.lock_group(group_id)
    if group.status != 'open':
        raise EnrollmentRuleError('El grupo está cerrado.')
    up = _check_student(_lock_student(user_program_id), group)
    slot_subject_id = _check_subject(up, group, slot_subject_id)

    existing = CourseEnrollment.query.filter_by(
        user_program_id=up.id, subject_id=group.subject_id,
        academic_period_id=group.academic_period_id).first()
    if existing is not None and existing.status != 'dropped':
        raise EnrollmentRuleError('El estudiante ya está inscrito en esa materia en este periodo.')
    if course_group_service.enrolled_count(group.id) >= group.capacity:
        raise EnrollmentRuleError('El grupo no tiene cupo.')
    attempt = next_attempt(up.id, group.subject_id)
    if attempt > MAX_ATTEMPTS:
        raise EnrollmentRuleError('Agotó los tres intentos de esta materia.')

    if existing is not None:   # re-enrolling after a drop in the same period
        enrollment = existing
        enrollment.status = 'enrolled'
        enrollment.dropped_at = enrollment.dropped_by = None
    else:
        enrollment = CourseEnrollment(
            user_program_id=up.id, subject_id=group.subject_id,
            academic_period_id=group.academic_period_id, created_by=actor_id)
        db.session.add(enrollment)
    enrollment.course_group_id = group.id
    enrollment.slot_subject_id = slot_subject_id
    enrollment.attempt = attempt
    enrollment.attempt_type = ATTEMPT_TYPES[attempt]

    UserHistoryService.log_action(
        user_id=up.user_id, action='course_enrolled', admin_id=actor_id,
        user_program_id=up.id,
        details={'subject': group.subject.name, 'group': group.group_code,
                 'period_id': group.academic_period_id, 'attempt': enrollment.attempt_type},
    )
    try:
        db.session.commit()
    except IntegrityError:   # a concurrent enrollment won the unique constraint
        db.session.rollback()
        raise EnrollmentRuleError(
            'El estudiante ya está inscrito en esa materia en este periodo.')
    return enrollment


def drop(enrollment_id: int, actor_id: int) -> CourseEnrollment:
    """Remove a student from a group; the row stays as 'dropped' and frees the seat."""
    enrollment = db.session.get(CourseEnrollment, enrollment_id)
    if enrollment is None or enrollment.status == 'dropped':
        raise NotFoundError('Inscripción no encontrada.')
    if enrollment.course_group_id:
        course_group_service.lock_group(enrollment.course_group_id)
    enrollment.status = 'dropped'
    enrollment.dropped_at = now_local()
    enrollment.dropped_by = actor_id
    UserHistoryService.log_action(
        user_id=enrollment.user_program.user_id, action='course_dropped', admin_id=actor_id,
        user_program_id=enrollment.user_program_id,
        details={'subject': enrollment.subject.name, 'period_id': enrollment.academic_period_id},
    )
    db.session.commit()
    return enrollment


def _student_name(up: UserProgram) -> str:
    return f'{up.user.first_name} {up.user.last_name}'.strip()


def enroll_semester(group_ids: Iterable[int], user_program_ids: Iterable[int],
                    actor_id: int) -> dict:
    """
    Enroll each student in every given group whose subject's suggested
    semester is the student's current semester. Electives are skipped (the
    coordinator picks those one by one). Returns what happened per student.
    """
    groups = [g for g in (db.session.get(CourseGroup, gid) for gid in group_ids) if g]
    if len({g.academic_period_id for g in groups}) > 1:
        raise EnrollmentRuleError('Todos los grupos deben ser del mismo periodo.')
    enrolled, skipped = 0, []
    for up_id in user_program_ids:
        up = db.session.get(UserProgram, up_id)
        if up is None:
            continue
        semester = up.current_semester or 1
        matching = [g for g in groups if g.subject.kind == 'required'
                    and g.subject.suggested_semester == semester]
        if not matching:
            skipped.append({'name': _student_name(up),
                            'reason': f'No hay grupos de materias de {semester}º semestre.'})
            continue
        for group in matching:
            try:
                enroll(group.id, up.id, actor_id)
                enrolled += 1
            except DomainError as exc:
                db.session.rollback()
                skipped.append({'name': _student_name(up),
                                'reason': f'{group.subject.name}: {exc}'})
    return {'enrolled': enrolled, 'skipped': skipped}


def load_for(user_program_id: int, *, include_dropped: bool = False) -> list[dict]:
    """The student's enrollments grouped by period, newest period first."""
    from app.models.academic_period import AcademicPeriod

    query = (CourseEnrollment.query
             .join(AcademicPeriod, AcademicPeriod.id == CourseEnrollment.academic_period_id)
             .options(joinedload(CourseEnrollment.subject),
                      joinedload(CourseEnrollment.slot_subject),
                      joinedload(CourseEnrollment.academic_period),
                      joinedload(CourseEnrollment.course_group).joinedload(CourseGroup.teacher))
             .filter(CourseEnrollment.user_program_id == user_program_id))
    if not include_dropped:
        query = query.filter(CourseEnrollment.status != 'dropped')
    rows = query.order_by(AcademicPeriod.start_date.desc(), CourseEnrollment.id).all()

    periods: 'OrderedDict[int, dict]' = OrderedDict()
    for e in rows:
        bucket = periods.setdefault(e.academic_period_id, {
            'period': e.academic_period, 'items': []})
        group = e.course_group
        teacher = group.teacher if group else None
        bucket['items'].append({
            'enrollment': e,
            'subject': e.subject,
            'slot_name': e.slot_subject.name if e.slot_subject else None,
            'group_code': group.group_code if group else None,
            'teacher_name': f'{teacher.first_name} {teacher.last_name}'.strip() if teacher else None,
            'schedule': group.schedule if group else None,
            'location': group.location if group else None,
            'attempt_type': e.attempt_type,
            'status': e.status,
        })
    return list(periods.values())

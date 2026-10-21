# app/services/course_group_service.py
"""
Course groups: a subject offered in an academic period (phase 6B1).

The coordinator owns groups (subject, group code, teacher, capacity, room,
schedule); the teacher owns the grades (phase 6B2).
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.course_enrollment import CourseEnrollment
from app.models.course_group import CourseGroup
from app.models.subject import Subject
from app.models.user import User
from app.schemas.curriculum import CourseGroupIn
from app.services.errors import DomainError, NotFoundError


class CourseGroupError(DomainError):
    """Business rule of course groups."""


def get_group(group_uuid) -> Optional[CourseGroup]:
    return CourseGroup.by_uuid(group_uuid)


def lock_group(group_id: int) -> CourseGroup:
    group = (CourseGroup.query.filter_by(id=group_id)
             .with_for_update().populate_existing().first())
    if group is None:
        raise NotFoundError('Grupo no encontrado.')
    return group


def enrolled_count(group_id: int) -> int:
    return (db.session.query(db.func.count(CourseEnrollment.id))
            .filter_by(course_group_id=group_id, status='enrolled').scalar()) or 0


def enrolled_counts(group_ids: Iterable[int]) -> dict[int, int]:
    """Enrolled students per group in one query."""
    ids = list(group_ids)
    if not ids:
        return {}
    rows = (db.session.query(CourseEnrollment.course_group_id, db.func.count(CourseEnrollment.id))
            .filter(CourseEnrollment.course_group_id.in_(ids),
                    CourseEnrollment.status == 'enrolled')
            .group_by(CourseEnrollment.course_group_id).all())
    return {gid: n for gid, n in rows}


def _row(group: CourseGroup, enrolled: int) -> dict:
    teacher = group.teacher
    return {
        'group': group,
        'subject': group.subject,
        'teacher_name': (f'{teacher.first_name} {teacher.last_name}'.strip() if teacher else None),
        'enrolled': enrolled,
        'capacity': group.capacity,
    }


def groups_for(program_id: int, period_id: int) -> list[dict]:
    groups = (CourseGroup.query
              .join(Subject, Subject.id == CourseGroup.subject_id)
              .options(joinedload(CourseGroup.subject), joinedload(CourseGroup.teacher))
              .filter(CourseGroup.program_id == program_id,
                      CourseGroup.academic_period_id == period_id)
              .order_by(Subject.suggested_semester.nullslast(), Subject.name,
                        CourseGroup.group_code)
              .all())
    counts = enrolled_counts(g.id for g in groups)
    return [_row(g, counts.get(g.id, 0)) for g in groups]


def _validate_teacher(teacher_id: Optional[int]) -> None:
    if teacher_id is None:
        return
    teacher = db.session.get(User, teacher_id)
    if teacher is None or not teacher.is_active or not teacher.is_internal:
        raise CourseGroupError('El docente debe ser un usuario interno activo.')


def save_group(program_id: int, data: CourseGroupIn, actor_id: int,
               group_id: Optional[int] = None) -> CourseGroup:
    subject = db.session.get(Subject, data.subject_id)
    if subject is None or subject.plan.program_id != program_id:
        raise CourseGroupError('La materia no pertenece a este programa.')
    if subject.kind == 'elective_slot':
        raise CourseGroupError(
            'Un hueco de optativa no se imparte: crea el grupo con una optativa del banco.')
    if not subject.is_active:
        raise CourseGroupError('La materia está dada de baja del plan.')
    if db.session.get(AcademicPeriod, data.academic_period_id) is None:
        raise CourseGroupError('El periodo académico no existe.')
    _validate_teacher(data.teacher_id)

    clash = CourseGroup.query.filter(
        CourseGroup.subject_id == data.subject_id,
        CourseGroup.academic_period_id == data.academic_period_id,
        CourseGroup.group_code == data.group_code,
        CourseGroup.id != (group_id or 0),
    ).first()
    if clash is not None:
        raise CourseGroupError(
            f'Ya existe el grupo "{data.group_code}" de esa materia en el periodo.')

    if group_id is None:
        group = CourseGroup(program_id=program_id, created_by=actor_id, status='open')
        db.session.add(group)
    else:
        group = lock_group(group_id)
        if group.program_id != program_id:
            raise NotFoundError('Grupo no encontrado.')
        taken = enrolled_count(group.id)
        if data.capacity < taken:
            raise CourseGroupError(
                f'El cupo no puede ser menor que los {taken} alumnos inscritos.')
        has_history = CourseEnrollment.query.filter_by(course_group_id=group.id).first()
        if (group.subject_id != data.subject_id
                or group.academic_period_id != data.academic_period_id) and has_history:
            raise CourseGroupError(
                'No se puede cambiar la materia ni el periodo de un grupo con alumnos.')
    for field in ('subject_id', 'academic_period_id', 'group_code', 'capacity',
                  'teacher_id', 'location', 'schedule'):
        setattr(group, field, getattr(data, field))
    try:
        db.session.commit()
    except IntegrityError:   # a concurrent save took the same group code
        db.session.rollback()
        raise CourseGroupError(
            f'Ya existe el grupo "{data.group_code}" de esa materia en el periodo.')
    return group


def roster(group_id: int) -> list[dict]:
    rows = (CourseEnrollment.query
            .filter_by(course_group_id=group_id, status='enrolled')
            .all())
    out = []
    for e in rows:
        user = e.user_program.user
        out.append({
            'enrollment': e,
            'user': user,
            'full_name': f'{user.last_name} {user.mother_last_name or ""} {user.first_name}'
                         .replace('  ', ' ').strip(),
            'control_number': user.control_number,
            'attempt_type': e.attempt_type,
        })
    return sorted(out, key=lambda r: r['full_name'].lower())

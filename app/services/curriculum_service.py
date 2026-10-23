# app/services/curriculum_service.py
"""
Versioned study plans (retícula) and their subjects — phase 6B1.

A student program follows the plan version it entered with; publishing a
new version only affects later students. Exactly one version per program is
current. Electives: a plan has slots ("Optativa I", with a suggested
semester) and a bank of elective subjects; enrolling in an elective fills
one open slot of the student's plan.
"""
from __future__ import annotations

from typing import Optional

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.curriculum_plan import CurriculumPlan
from app.models.subject import Subject
from app.models.user_program import UserProgram
from app.schemas.curriculum import SubjectIn
from app.services.errors import DomainError, NotFoundError
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local


class CurriculumError(DomainError):
    """Business rule of study plans."""


def plans_for_program(program_id: int) -> list[CurriculumPlan]:
    return (CurriculumPlan.query.filter_by(program_id=program_id)
            .order_by(CurriculumPlan.version.desc()).all())


def current_plan(program_id: int) -> Optional[CurriculumPlan]:
    return CurriculumPlan.query.filter_by(program_id=program_id, is_current=True).first()


def get_plan(plan_id: int) -> CurriculumPlan:
    plan = db.session.get(CurriculumPlan, plan_id)
    if plan is None:
        raise NotFoundError('Plan de estudios no encontrado.')
    return plan


def get_subject(subject_id: int) -> Subject:
    subject = db.session.get(Subject, subject_id)
    if subject is None:
        raise NotFoundError('Materia no encontrada.')
    return subject


def subjects_of(plan_id: int, *, include_inactive: bool = False) -> list[Subject]:
    query = Subject.query.filter_by(plan_id=plan_id)
    if not include_inactive:
        query = query.filter_by(is_active=True)
    return query.order_by(Subject.suggested_semester.nullslast(), Subject.sequence,
                          Subject.id).all()


def _lock_program_plans(program_id: int) -> list[CurriculumPlan]:
    return (CurriculumPlan.query.filter_by(program_id=program_id)
            .with_for_update().populate_existing().all())


def create_version(program_id: int, actor_id: int, *,
                   copy_from_plan_id: Optional[int] = None) -> CurriculumPlan:
    """New (not current) version; copies the subjects of `copy_from_plan_id` or of the current one."""
    plans = _lock_program_plans(program_id)
    version = max((p.version for p in plans), default=0) + 1
    source_id = copy_from_plan_id or next((p.id for p in plans if p.is_current), None)
    source = get_plan(source_id) if source_id else None
    if source is not None and source.program_id != program_id:
        raise CurriculumError('La versión de origen pertenece a otro programa.')

    plan = CurriculumPlan(
        program_id=program_id, version=version, is_current=False, created_by=actor_id,
        name=(source.name if source else 'Plan de estudios'),
    )
    db.session.add(plan)
    db.session.flush()
    if source is not None:
        for subject in subjects_of(source.id, include_inactive=False):
            db.session.add(Subject(
                plan_id=plan.id, key=subject.key, name=subject.name, credits=subject.credits,
                suggested_semester=subject.suggested_semester, kind=subject.kind,
                sequence=subject.sequence, is_active=True,
            ))
    db.session.commit()
    return plan


def set_current(plan_id: int, actor_id: int) -> CurriculumPlan:
    """Make `plan_id` the current version of its program (the others stop being current)."""
    plan = get_plan(plan_id)
    # Two steps: the partial unique index (one current per program) is checked
    # per statement, so the old current must be cleared before the new one is set.
    for other in _lock_program_plans(plan.program_id):
        other.is_current = False
    db.session.flush()
    plan.is_current = True
    db.session.commit()
    return plan


def save_subject(plan_id: int, data: SubjectIn, actor_id: int,
                 subject_id: Optional[int] = None) -> Subject:
    get_plan(plan_id)
    if data.key:
        clash = Subject.query.filter(Subject.plan_id == plan_id, Subject.key == data.key,
                                     Subject.id != (subject_id or 0)).first()
        if clash is not None:
            raise CurriculumError(f'La clave "{data.key}" ya existe en esta versión del plan.')
    if data.kind == 'elective' and data.suggested_semester is not None:
        raise CurriculumError('Una optativa del banco no lleva semestre sugerido.')

    if subject_id is not None:
        current = get_subject(subject_id)
        if current.kind != data.kind and _subject_in_use(subject_id):
            raise CurriculumError(
                'No se puede cambiar el tipo de una materia que ya tiene grupos o inscripciones.')

    if subject_id is None:
        subject = Subject(plan_id=plan_id)
        if data.sequence is None:
            data.sequence = (db.session.query(db.func.max(Subject.sequence))
                             .filter_by(plan_id=plan_id).scalar() or 0) + 1
        db.session.add(subject)
    else:
        subject = get_subject(subject_id)
        if subject.plan_id != plan_id:
            raise NotFoundError('Materia no encontrada.')
    for field in ('name', 'key', 'credits', 'suggested_semester', 'kind'):
        setattr(subject, field, getattr(data, field))
    if data.sequence is not None:
        subject.sequence = data.sequence
    db.session.commit()
    return subject


def _subject_in_use(subject_id: int) -> bool:
    from app.models.course_group import CourseGroup
    return bool(
        CourseGroup.query.filter_by(subject_id=subject_id).first()
        or CourseEnrollment.query.filter(
            (CourseEnrollment.subject_id == subject_id)
            | (CourseEnrollment.slot_subject_id == subject_id)).first()
    )


def deactivate_subject(subject_id: int, actor_id: int) -> Subject:
    """Hide a subject from new groups; existing enrollments keep pointing at it."""
    subject = get_subject(subject_id)
    subject.is_active = False
    db.session.commit()
    return subject


def _covered_slot_ids(user_program_id: int) -> set[int]:
    rows = (db.session.query(CourseEnrollment.slot_subject_id)
            .filter(CourseEnrollment.user_program_id == user_program_id,
                    CourseEnrollment.slot_subject_id.isnot(None),
                    CourseEnrollment.status != 'dropped')
            .all())
    return {slot_id for (slot_id,) in rows}


def open_slots(user_program: UserProgram) -> list[Subject]:
    """Elective slots of the student's plan not yet filled by an enrolled elective."""
    if not user_program.curriculum_plan_id:
        return []
    covered = _covered_slot_ids(user_program.id)
    return [s for s in subjects_of(user_program.curriculum_plan_id)
            if s.kind == 'elective_slot' and s.id not in covered]


def change_student_plan(user_program_id: int, plan_id: int, reason: str,
                        actor_id: int) -> UserProgram:
    """Move a student to another version of the same program's plan (reason required)."""
    reason = (reason or '').strip()
    if not reason:
        raise CurriculumError('El motivo es obligatorio.')
    up = (UserProgram.query.filter_by(id=user_program_id)
          .with_for_update().populate_existing().first())
    if up is None:
        raise NotFoundError('Estudiante no encontrado.')
    plan = get_plan(plan_id)
    if CourseEnrollment.query.filter_by(user_program_id=up.id, status='enrolled').first():
        raise CurriculumError(
            'El estudiante tiene materias inscritas: dalo de baja de sus grupos antes de '
            'cambiar la versión del plan.')
    if plan.program_id != up.program_id:
        raise CurriculumError('La versión del plan pertenece a otro programa.')
    previous = up.curriculum_plan.version if up.curriculum_plan else None
    up.curriculum_plan_id = plan.id
    UserHistoryService.log_action(
        user_id=up.user_id, action='curriculum_plan_changed', admin_id=actor_id,
        user_program_id=up.id,
        details={'from_version': previous, 'to_version': plan.version, 'reason': reason,
                 'at': now_local().isoformat()},
    )
    db.session.commit()
    return up

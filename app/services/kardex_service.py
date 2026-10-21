# app/services/kardex_service.py
"""
The kardex of a student program — phase 6B2.

Built from `course_enrollment` rows (one per attempt) against the plan
version the student follows: required subjects by suggested semester, and
elective slots filled by the elective that covered them. Average = mean of
the passing grade of each passed subject (owner's decision; NP never
passes, so it never enters). `complete` = every required subject and every
slot passed — what suggests graduation.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict

from sqlalchemy.orm import joinedload

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.course_enrollment import CourseEnrollment
from app.models.subject import Subject
from app.models.user_program import UserProgram
from app.services.errors import NotFoundError
from app.services.grading_service import ATTEMPT_LABELS, display

STATUS_LABELS = {'passed': 'Aprobada', 'failed': 'Reprobada', 'enrolled': 'Cursando',
                 'pending': 'Pendiente'}


def _attempts(user_program_id: int) -> list[CourseEnrollment]:
    return (CourseEnrollment.query
            .join(AcademicPeriod, AcademicPeriod.id == CourseEnrollment.academic_period_id)
            .options(joinedload(CourseEnrollment.academic_period),
                     joinedload(CourseEnrollment.subject))
            .filter(CourseEnrollment.user_program_id == user_program_id,
                    CourseEnrollment.status != 'dropped')
            .order_by(AcademicPeriod.start_date, CourseEnrollment.id)
            .all())


def _row(subject: Subject, attempts: list[CourseEnrollment], *, slot: Subject = None) -> dict:
    passed = next((a for a in attempts if a.result == 'passed'), None)
    if passed is not None:
        status = 'passed'
    elif any(a.status == 'enrolled' for a in attempts):
        status = 'enrolled'
    elif attempts:
        status = 'failed'
    else:
        status = 'pending'
    taken = passed.subject if passed else (attempts[-1].subject if attempts else None)
    credits = (taken.credits if taken is not None and taken.credits is not None
               else subject.credits)
    return {
        'subject': subject,
        'slot': slot,
        'taken_subject': taken if slot is not None else None,
        'credits': credits,
        'attempts': [{
            'period_name': a.academic_period.name,
            'attempt_label': ATTEMPT_LABELS.get(a.attempt_type, a.attempt_type),
            'value': display(a.grade, a.grade_mark) if a.status == 'graded' else '',
            'result': a.result,
            'in_progress': a.status == 'enrolled',
        } for a in attempts],
        'status': status,
        'status_label': STATUS_LABELS[status],
        'final_grade': passed.grade if passed else None,
    }


def kardex(user_program_id: int) -> dict:
    up = db.session.get(UserProgram, user_program_id)
    if up is None:
        raise NotFoundError('Estudiante no encontrado.')
    plan = up.curriculum_plan
    subjects = (Subject.query.filter_by(plan_id=plan.id).order_by(
        Subject.suggested_semester.nullslast(), Subject.sequence, Subject.id).all()
        if plan else [])

    by_subject, by_slot = defaultdict(list), defaultdict(list)
    for a in _attempts(up.id):
        by_subject[a.subject_id].append(a)
        if a.slot_subject_id:
            by_slot[a.slot_subject_id].append(a)

    semesters: 'OrderedDict[int, list]' = OrderedDict()
    units = []
    for s in subjects:
        if s.kind == 'required' and (s.is_active or by_subject[s.id]):
            row = _row(s, by_subject[s.id])
        elif s.kind == 'elective_slot':
            row = _row(s, by_slot[s.id], slot=s)
        else:
            continue
        semesters.setdefault(s.suggested_semester or 0, []).append(row)
        if s.is_active or row['status'] == 'passed':
            units.append(row)

    passed = [r for r in units if r['status'] == 'passed']
    grades = [r['final_grade'] for r in passed if r['final_grade'] is not None]
    credits_total = sum(r['credits'] or 0 for r in units)
    credits_earned = sum(r['credits'] or 0 for r in passed)
    return {
        'user_program': up,
        'plan': plan,
        'semesters': [{'number': n, 'rows': rows} for n, rows in semesters.items()],
        'passed_count': len(passed),
        'total_count': len(units),
        'credits_earned': credits_earned,
        'credits_total': credits_total,
        'average': round(sum(grades) / len(grades), 2) if grades else None,
        'progress': round(100 * len(passed) / len(units)) if units else 0,
        'complete': bool(units) and len(passed) == len(units),
    }


def has_passed(user_program_id: int, subject_id: int) -> bool:
    return CourseEnrollment.query.filter_by(
        user_program_id=user_program_id, subject_id=subject_id, result='passed').first() is not None

# app/services/academic_documents_service.py
"""
Informative PDFs of the academic record (phase 6B3): kardex, report card
(boleta) per period and group acta.

The context builders are pure data (no request, no current_user); `render_pdf`
needs an application context for the templates. The documents are informative
only (no official signature or folio yet) and say so in the letterhead.
"""
from __future__ import annotations

import re
from typing import Optional

from flask import current_app, render_template

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.course_enrollment import CourseEnrollment
from app.models.course_group import CourseGroup
from app.models.user_program import UserProgram
from app.services import grading_service, kardex_service
from app.services.errors import DomainError, NotFoundError
from app.services.grading_service import ATTEMPT_LABELS, display
from app.utils.datetime_utils import now_local

IN_CAPTURE = 'En captura'
RESULT_LABELS = {'passed': 'Aprobada', 'failed': 'Reprobada'}


def _full_name(user) -> str:
    return (f'{user.first_name} {user.last_name} {user.mother_last_name or ""}'
            .replace('  ', ' ').strip())


def _student(up: UserProgram) -> dict:
    plan = up.curriculum_plan
    return {
        'full_name': _full_name(up.user),
        'control_number': up.user.control_number or '—',
        'program_name': up.program.name if up.program else '—',
        'plan_version': plan.version if plan else None,
    }


def _user_program(up_id: int) -> UserProgram:
    up = db.session.get(UserProgram, up_id)
    if up is None:
        raise NotFoundError('Estudiante no encontrado.')
    return up


def safe_filename(*parts) -> str:
    """Join parts with '_' keeping only [A-Za-z0-9._-]."""
    text = '_'.join(str(p) for p in parts if p not in (None, ''))
    return re.sub(r'[^A-Za-z0-9._-]+', '-', text).strip('-') or 'documento'


def _rows_of_period(up_id: int, period_id: int) -> list[CourseEnrollment]:
    return (CourseEnrollment.query
            .filter(CourseEnrollment.user_program_id == up_id,
                    CourseEnrollment.academic_period_id == period_id,
                    CourseEnrollment.status != 'dropped')
            .order_by(CourseEnrollment.id).all())


def periods_of(up_id: int) -> list[AcademicPeriod]:
    """Periods in which the student has at least one (non-dropped) row, oldest first."""
    return (AcademicPeriod.query
            .filter(AcademicPeriod.id.in_(
                db.session.query(CourseEnrollment.academic_period_id).filter(
                    CourseEnrollment.user_program_id == up_id,
                    CourseEnrollment.status != 'dropped')))
            .order_by(AcademicPeriod.start_date, AcademicPeriod.id).all())


def kardex_context(up_id: int) -> dict:
    kd = kardex_service.kardex(up_id)
    return {'kd': kd, 'student': _student(kd['user_program']),
            'issued_at': now_local(), 'doc_title': 'Kardex'}


def report_card_context(up_id: int, period_id: int) -> dict:
    up = _user_program(up_id)
    period = db.session.get(AcademicPeriod, period_id)
    rows = _rows_of_period(up_id, period_id) if period is not None else []
    if not rows:
        raise NotFoundError('Periodo no encontrado.')
    out, grades = [], []
    for e in rows:
        in_capture = e.status == 'enrolled'
        if not in_capture and e.result == 'passed' and e.grade is not None:
            grades.append(e.grade)
        out.append({
            'key': e.subject.key or '—',
            'name': e.subject.name,
            'credits': e.subject.credits,
            'group': e.course_group.group_code if e.course_group else 'Historial',
            'attempt_label': ATTEMPT_LABELS.get(e.attempt_type, e.attempt_type),
            'value': IN_CAPTURE if in_capture else display(e.grade, e.grade_mark),
            'result': '—' if in_capture else RESULT_LABELS.get(e.result, '—'),
            'in_capture': in_capture,
        })
    return {
        'student': _student(up), 'period': period, 'rows': out,
        'average': round(sum(grades) / len(grades), 2) if grades else None,
        'issued_at': now_local(), 'doc_title': 'Boleta de calificaciones',
    }


def acta_context(group_id: int) -> dict:
    group = db.session.get(CourseGroup, group_id)
    if group is None:
        raise NotFoundError('Grupo no encontrado.')
    if group.status != 'closed':
        raise DomainError('El acta aún no está cerrada.')
    teacher = group.teacher
    return {
        'group': group, 'subject': group.subject, 'period': group.academic_period,
        'program_name': group.program.name if group.program else '—',
        'teacher_name': _full_name(teacher) if teacher else 'Sin asignar',
        'rows': grading_service.acta_rows(group.id),
        'issued_at': now_local(), 'doc_title': 'Acta de calificaciones',
    }


def render_pdf(template: str, **ctx) -> bytes:
    """Render a `pdf/*.html` template to PDF bytes (logos load from the static folder)."""
    from weasyprint import HTML
    html = render_template(template, **ctx)
    base = current_app.static_folder.rstrip('/\\') + '/'
    return HTML(string=html, base_url=base).write_pdf()


def pick_user_program(user, program_id: Optional[int]) -> Optional[UserProgram]:
    """The user's own enrolled link (`program_id` picks one; else the current one)."""
    options = sorted((up for up in (user.user_program or [])
                      if up.admission_status == 'enrolled'),
                     key=lambda up: (up.program.name if up.program else '', up.id))
    if program_id is not None:
        return next((o for o in options if o.program_id == program_id), None)
    up = user.current_user_program()
    if up is not None and up in options:
        return up
    return options[0] if options else None

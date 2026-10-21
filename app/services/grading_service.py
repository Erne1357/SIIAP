# app/services/grading_service.py
"""
Grades and actas — phase 6B2.

The teacher of a group (whoever `course_group.teacher_id` names) captures a
draft (0–100 or 'NP') while capture is open, then closes the acta: every
grade becomes final (status 'graded'), the group closes, and a failed
special attempt withdraws the student automatically (owner's decision).
After that a grade changes only through a correction the teacher requests
and postgraduate_admin decides.

Capture is open while the group is open and today falls inside the period's
window (`grade_capture_start/end`; both empty = no restriction) or before
the group's own extension (`capture_until`).
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Optional

from app import db
from app.models.course_enrollment import PASSING_GRADE, CourseEnrollment
from app.models.course_group import CourseGroup
from app.models.grade_correction import GradeCorrection
from app.services import course_group_service
from app.services.errors import DomainError, NotFoundError
from app.services.notification_service import NotificationService
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import format_date_es, now_local

logger = logging.getLogger(__name__)
_GRADE_RE = re.compile(r'[0-9]{1,3}')

ATTEMPT_LABELS = {'ordinary': 'Ordinario', 'repeat': 'Repetición', 'special': 'Especial'}
NO_SHOW = 'NP'


class GradingError(DomainError):
    """Business rule of grades and actas."""


# ── Values ───────────────────────────────────────────────────────────────────

def parse_value(raw) -> Optional[tuple[Optional[int], Optional[str]]]:
    """'85' -> (85, None); 'NP' -> (None, 'NP'); blank -> None; anything else -> GradingError."""
    text = ('' if raw is None else str(raw)).strip().upper()
    if not text:
        return None
    if text == NO_SHOW:
        return None, NO_SHOW
    if not _GRADE_RE.fullmatch(text) or not 0 <= int(text) <= 100:
        raise GradingError('La calificación debe ser un número entero de 0 a 100 o NP.')
    return int(text), None


def result_of(grade: Optional[int], mark: Optional[str]) -> str:
    return 'passed' if mark is None and grade is not None and grade >= PASSING_GRADE else 'failed'


def display(grade, mark) -> str:
    return mark or ('' if grade is None else str(grade))


# ── Capture window ───────────────────────────────────────────────────────────

def capture_open(group: CourseGroup, today: Optional[date] = None) -> bool:
    if group.status != 'open':
        return False
    today = today or now_local().date()
    if group.capture_until is not None and today <= group.capture_until:
        return True
    period = group.academic_period
    start, end = period.grade_capture_start, period.grade_capture_end
    if start is None and end is None:
        return True
    return (start is None or start <= today) and (end is None or today <= end)


def capture_window_text(group: CourseGroup) -> Optional[str]:
    """Spanish description of the window, for the teacher's notice."""
    period = group.academic_period
    parts = []
    if period.grade_capture_start or period.grade_capture_end:
        start = format_date_es(period.grade_capture_start) if period.grade_capture_start else '—'
        end = format_date_es(period.grade_capture_end) if period.grade_capture_end else '—'
        parts.append(f'Captura del periodo: {start} a {end}.')
    if group.capture_until:
        parts.append(f'Captura ampliada para este grupo hasta el {format_date_es(group.capture_until)}.')
    return ' '.join(parts) or None


# ── Acta ─────────────────────────────────────────────────────────────────────

def _teacher_group(group_id: int, actor_id: int, *, lock: bool = False) -> CourseGroup:
    group = course_group_service.lock_group(group_id) if lock else db.session.get(CourseGroup, group_id)
    if group is None or group.teacher_id != actor_id:
        raise NotFoundError('Grupo no encontrado.')
    return group


def _rows_of(group_id: int, statuses=('enrolled', 'graded')) -> list[CourseEnrollment]:
    return (CourseEnrollment.query
            .filter(CourseEnrollment.course_group_id == group_id,
                    CourseEnrollment.status.in_(statuses))
            .all())


def acta_rows(group_id: int) -> list[dict]:
    """The acta of a group: one row per student, with draft or final grade."""
    rows = _rows_of(group_id)
    pending = {c.course_enrollment_id: c for c in GradeCorrection.query.filter(
        GradeCorrection.course_enrollment_id.in_([r.id for r in rows] or [0]),
        GradeCorrection.status == 'pending').all()}
    out = []
    for e in rows:
        user = e.user_program.user
        out.append({
            'enrollment': e,
            'full_name': f'{user.last_name} {user.mother_last_name or ""} {user.first_name}'
                         .replace('  ', ' ').strip(),
            'control_number': user.control_number,
            'attempt_type': e.attempt_type,
            'attempt_label': ATTEMPT_LABELS.get(e.attempt_type, e.attempt_type),
            'value': display(e.grade, e.grade_mark),
            'final': e.status == 'graded',
            'result': e.result,
            'pending_correction': pending.get(e.id),
        })
    return sorted(out, key=lambda r: r['full_name'].lower())


def save_draft(group_id: int, grades: dict, actor_id: int) -> int:
    """Save draft values {enrollment_id: '85'|'NP'|''} for the teacher's own group."""
    group = _teacher_group(group_id, actor_id, lock=True)
    if not capture_open(group):
        raise GradingError('La captura de calificaciones de este grupo no está abierta.')
    rows = {e.id: e for e in _rows_of(group.id, statuses=('enrolled',))}
    parsed = {int(k): parse_value(v) for k, v in grades.items() if int(k) in rows}
    for enrollment_id, value in parsed.items():
        rows[enrollment_id].grade, rows[enrollment_id].grade_mark = value or (None, None)
    db.session.commit()
    return len(parsed)


def close_acta(group_id: int, actor_id: int) -> dict:
    """Make every grade final, close the group and apply the special-attempt rule."""
    from app.services import permanence_service

    group = _teacher_group(group_id, actor_id, lock=True)
    if not capture_open(group):
        raise GradingError('El acta ya está cerrada o la captura no está abierta.')
    rows = _rows_of(group.id, statuses=('enrolled',))
    if not rows:
        raise GradingError('El grupo no tiene estudiantes inscritos.')
    missing = [e for e in rows if e.grade is None and e.grade_mark is None]
    if missing:
        raise GradingError(f'Faltan {len(missing)} calificaciones por capturar.')

    now = now_local()
    failed_special = []
    for e in rows:
        e.status = 'graded'
        e.result = result_of(e.grade, e.grade_mark)
        e.graded_at, e.graded_by = now, actor_id
        UserHistoryService.log_action(
            user_id=e.user_program.user_id, action='grade_published', admin_id=actor_id,
            user_program_id=e.user_program_id,
            details={'subject': e.subject.name, 'grade': display(e.grade, e.grade_mark),
                     'result': e.result, 'attempt': e.attempt_type},
        )
        NotificationService.create_notification(
            user_id=e.user_program.user_id, notification_type='grade_published',
            title=f'Calificación publicada — {e.subject.name}',
            message=f'Tu calificación de {e.subject.name} es {display(e.grade, e.grade_mark)}.',
            priority='medium', action_url='/kardex/',
        )
        if e.attempt_type == 'special' and e.result == 'failed':
            failed_special.append(e)
    group.status = 'closed'
    group.closed_at, group.closed_by = now, actor_id
    db.session.commit()

    withdrawn, to_review = [], []
    for e in failed_special:
        up = e.user_program
        name = f'{up.user.first_name} {up.user.last_name}'.strip()
        if up.academic_status not in ('active', 'on_leave', None):
            to_review.append(name)          # already graduated/withdrawn: a human decides
            continue
        try:
            permanence_service.withdraw(
                up.id, f'Reprobó en especial: {e.subject.name} ({e.academic_period.name}).',
                actor_id)
            withdrawn.append(name)
        except DomainError as exc:
            db.session.rollback()
            logger.warning('[grading] automatic withdrawal failed for up=%s: %s', up.id, exc)
            to_review.append(name)
    if (withdrawn or to_review) and group.program and group.program.coordinator_id:
        parts = [f'Al cerrar el acta de {group.subject.name} (grupo {group.group_code})']
        if withdrawn:
            parts.append(f'quedaron en baja definitiva por reprobar en especial: '
                         f'{", ".join(withdrawn)}.')
        if to_review:
            parts.append(f'Reprobaron en especial y requieren revisión manual: '
                         f'{", ".join(to_review)}.')
        NotificationService.create_notification(
            user_id=group.program.coordinator_id, notification_type='automatic_withdrawal',
            title='Bajas definitivas por intento especial', message=' '.join(parts),
            priority='high', action_url='/coordinator/permanence',
        )
        db.session.commit()
    return {'graded': len(rows), 'withdrawn': withdrawn, 'to_review': to_review}


def extend_capture(group_id: int, until: date, reason: str, actor_id: int) -> CourseGroup:
    reason = (reason or '').strip()
    if not reason:
        raise GradingError('El motivo es obligatorio.')
    if until < now_local().date():
        raise GradingError('La nueva fecha límite no puede estar en el pasado.')
    group = course_group_service.lock_group(group_id)
    if group.status != 'open':
        raise GradingError('El acta de este grupo ya está cerrada.')
    group.capture_until = until
    group.capture_extension_reason = reason
    UserHistoryService.log_action(
        user_id=actor_id, action='grade_capture_extended', admin_id=actor_id,
        details={'group': str(group.uuid), 'subject': group.subject.name,
                 'until': until.isoformat(), 'reason': reason},
    )
    db.session.commit()
    return group


# ── Corrections ──────────────────────────────────────────────────────────────

def request_correction(enrollment_id: int, new_value, reason: str,
                       actor_id: int, *, group_id: Optional[int] = None) -> GradeCorrection:
    reason = (reason or '').strip()
    if not reason:
        raise GradingError('El motivo es obligatorio.')
    enrollment = db.session.get(CourseEnrollment, enrollment_id)
    if (enrollment is None or enrollment.course_group is None
            or enrollment.course_group.teacher_id != actor_id
            or (group_id is not None and enrollment.course_group_id != group_id)):
        raise NotFoundError('Calificación no encontrada.')
    if enrollment.status != 'graded':
        raise GradingError('Sólo se corrigen calificaciones de actas cerradas.')
    parsed = parse_value(new_value)
    if parsed is None:
        raise GradingError('Indica la calificación correcta.')
    if parsed == (enrollment.grade, enrollment.grade_mark):
        raise GradingError('La calificación nueva es igual a la actual.')
    if GradeCorrection.query.filter_by(course_enrollment_id=enrollment.id,
                                       status='pending').first():
        raise GradingError('Ya hay una solicitud de corrección pendiente para esta calificación.')
    correction = GradeCorrection(
        course_enrollment_id=enrollment.id, requested_by=actor_id, reason=reason,
        old_grade=enrollment.grade, old_mark=enrollment.grade_mark,
        new_grade=parsed[0], new_mark=parsed[1], status='pending')
    db.session.add(correction)
    UserHistoryService.log_action(
        user_id=enrollment.user_program.user_id, action='grade_correction_requested',
        admin_id=actor_id, user_program_id=enrollment.user_program_id,
        details={'subject': enrollment.subject.name,
                 'from': display(enrollment.grade, enrollment.grade_mark),
                 'to': display(*parsed), 'reason': reason},
    )
    db.session.commit()
    return correction


def pending_corrections() -> list[GradeCorrection]:
    return (GradeCorrection.query.filter_by(status='pending')
            .order_by(GradeCorrection.created_at).all())


def decide_correction(correction_id: int, approve: bool, notes: str,
                      actor_id: int) -> dict:
    """Approve (rewrite the grade) or reject. Never reverts an automatic withdrawal by itself."""
    correction = (GradeCorrection.query.filter_by(id=correction_id)
                  .with_for_update().populate_existing().first())
    if correction is None or correction.status != 'pending':
        raise NotFoundError('Solicitud no encontrada.')
    notes = (notes or '').strip() or None
    if not approve and not notes:
        raise GradingError('Indica el motivo del rechazo.')
    e = correction.enrollment
    if approve and (e.status != 'graded'
                    or (e.grade, e.grade_mark) != (correction.old_grade, correction.old_mark)):
        raise GradingError('La calificación cambió desde la solicitud; pide al docente una nueva.')
    review_withdrawal = special_now_failed = False
    correction.status = 'approved' if approve else 'rejected'
    correction.decided_by, correction.decided_at = actor_id, now_local()
    correction.decision_notes = notes
    if approve:
        old_result = e.result
        e.grade, e.grade_mark = correction.new_grade, correction.new_mark
        e.result = result_of(e.grade, e.grade_mark)
        review_withdrawal = (e.attempt_type == 'special' and old_result == 'failed'
                             and e.result == 'passed'
                             and e.user_program.academic_status == 'withdrawn')
        special_now_failed = (e.attempt_type == 'special' and old_result == 'passed'
                              and e.result == 'failed'
                              and e.user_program.academic_status in ('active', 'on_leave'))
        UserHistoryService.log_action(
            user_id=e.user_program.user_id, action='grade_corrected', admin_id=actor_id,
            user_program_id=e.user_program_id,
            details={'subject': e.subject.name,
                     'from': display(correction.old_grade, correction.old_mark),
                     'to': display(e.grade, e.grade_mark), 'reason': correction.reason},
        )
        NotificationService.create_notification(
            user_id=e.user_program.user_id, notification_type='grade_corrected',
            title=f'Calificación corregida — {e.subject.name}',
            message=(f'Tu calificación de {e.subject.name} cambió de '
                     f'{display(correction.old_grade, correction.old_mark)} a '
                     f'{display(e.grade, e.grade_mark)}.'),
            priority='medium', action_url='/kardex/',
        )
    if not approve:
        UserHistoryService.log_action(
            user_id=e.user_program.user_id, action='grade_correction_rejected',
            admin_id=actor_id, user_program_id=e.user_program_id,
            details={'subject': e.subject.name, 'notes': notes},
        )
    if correction.requested_by:
        NotificationService.create_notification(
            user_id=correction.requested_by, notification_type='grade_correction_decided',
            title='Solicitud de corrección ' + ('aprobada' if approve else 'rechazada'),
            message=f'{e.subject.name}: ' + (notes or 'sin comentarios.'),
            priority='medium', action_url='/teaching/',
        )
    db.session.commit()
    return {'correction': correction, 'review_withdrawal': review_withdrawal,
            'special_now_failed': special_now_failed}

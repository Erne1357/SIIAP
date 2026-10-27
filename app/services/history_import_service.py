# app/services/history_import_service.py
"""
Import of grade history from past periods — phase 6B3.

A CSV (`no_control, clave_materia, periodo, calificacion[, hueco]`) becomes
`course_enrollment` rows with no group: status 'graded', the attempt type
computed by period order (1st ordinary, 2nd repeat, 3rd special) and an
elective placed in the slot named by `hueco` or the first free one.

`preview` validates without writing; `execute` re-validates the same text
(the preview is never trusted) and writes each student in its own
transaction under the student-program row lock, so one bad student never
sinks the rest. A failed special does NOT withdraw automatically (owner's
decision): it is flagged and the program coordinator is notified.

Scope: unknown control number and a student outside the actor's programs
answer the same "Alumno no encontrado." (no existence oracle).
"""
from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.course_enrollment import ATTEMPT_TYPES, MAX_ATTEMPTS, CourseEnrollment
from app.models.subject import Subject
from app.models.user import User
from app.models.user_program import UserProgram
from app.services.errors import DomainError
from app.services.grading_service import ATTEMPT_LABELS, display, parse_value, result_of
from app.services.notification_service import NotificationService
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local

HEADERS = ('no_control', 'clave_materia', 'periodo', 'calificacion')
OPTIONAL_HEADERS = ('hueco',)
MAX_ROWS = 2000
TEMPLATE = 'no_control,clave_materia,periodo,calificacion,hueco\n'

NOT_FOUND = 'Alumno no encontrado.'

logger = logging.getLogger(__name__)


class HistoryImportError(DomainError):
    """The CSV as a whole cannot be read."""


@dataclass
class Row:
    line: int
    control: str
    key: str
    period_code: str
    raw_value: str
    slot_key: str
    errors: list = field(default_factory=list)
    up: Optional[UserProgram] = None
    subject: Optional[Subject] = None
    period: Optional[AcademicPeriod] = None
    value: Optional[tuple] = None
    attempt: Optional[int] = None
    slot: Optional[Subject] = None

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def result(self) -> Optional[str]:
        return result_of(*self.value) if self.value else None

    @property
    def attempt_type(self) -> Optional[str]:
        return ATTEMPT_TYPES.get(self.attempt) if self.attempt else None

    @property
    def special_failed(self) -> bool:
        return self.valid and self.attempt_type == 'special' and self.result == 'failed'

    def as_dict(self) -> dict:
        user = self.up.user if self.up else None
        return {
            'line': self.line,
            'control': self.control,
            'student': (f'{user.first_name} {user.last_name}' if user else ''),
            'subject': self.subject.name if self.subject else self.key,
            'subject_key': self.key,
            'period': self.period.name if self.period else self.period_code,
            'value': display(*self.value) if self.value else self.raw_value,
            'attempt_label': ATTEMPT_LABELS.get(self.attempt_type, ''),
            'slot': self.slot.name if self.slot else '',
            'result': self.result if self.valid else None,
            'special_failed': self.special_failed,
            'errors': list(self.errors),
        }


# ── Reading ──────────────────────────────────────────────────────────────────

def parse_csv(text: str) -> list[Row]:
    text = (text or '').lstrip('﻿')
    if not text.strip():
        raise HistoryImportError('El archivo está vacío.')
    header = text.splitlines()[0]
    # Excel in a Spanish locale saves with ';'.
    delimiter = ';' if header.count(';') > header.count(',') else ','
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fields = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [h for h in HEADERS if h not in fields]
    if missing:
        raise HistoryImportError('Faltan columnas: ' + ', '.join(missing) + '.')
    reader.fieldnames = fields
    rows = []
    for record in reader:
        cells = {k: (v or '').strip() for k, v in record.items() if k}
        if not any(cells.values()):
            continue
        if len(rows) >= MAX_ROWS:
            raise HistoryImportError(f'El archivo excede el máximo de {MAX_ROWS} filas.')
        rows.append(Row(line=reader.line_num, control=cells.get('no_control', ''),
                        key=cells.get('clave_materia', '').upper(),
                        period_code=cells.get('periodo', ''),
                        raw_value=cells.get('calificacion', ''),
                        slot_key=cells.get('hueco', '').upper()))
    if not rows:
        raise HistoryImportError('El archivo no tiene filas.')
    return rows


# ── Per-row resolution ───────────────────────────────────────────────────────

def _subject(plan_id: int, key: str, cache: dict) -> Optional[Subject]:
    if (plan_id, key) not in cache:
        cache[(plan_id, key)] = Subject.query.filter(
            Subject.plan_id == plan_id, db.func.upper(Subject.key) == key).first()
    return cache[(plan_id, key)]


def _resolve(row: Row, scope: Optional[set], today, caches: dict) -> None:
    """Fill student, subject, period and value; record the first errors found."""
    for name, value in (('no_control', row.control), ('clave_materia', row.key),
                        ('periodo', row.period_code), ('calificacion', row.raw_value)):
        if not value:
            row.errors.append(f'Falta {name}.')
    if row.errors:
        return

    user = User.query.filter_by(control_number=row.control).first()
    links = [up for up in (user.user_program if user else [])
             if up.admission_status == 'enrolled'
             and (scope is None or up.program_id in scope)]
    if not links:
        row.errors.append(NOT_FOUND)
        return
    with_plan = [up for up in links if up.curriculum_plan_id]
    if not with_plan:
        row.errors.append('El alumno no tiene plan de estudios asignado.')
        return
    matches = [up for up in with_plan
               if _subject(up.curriculum_plan_id, row.key, caches['subjects'])]
    if len(matches) > 1:
        row.errors.append('La clave existe en varios programas del alumno; no se puede decidir a cuál pertenece.')
        return
    if not matches:
        row.errors.append('La materia no existe en el plan del alumno.')
        return
    row.up = matches[0]
    row.subject = _subject(row.up.curriculum_plan_id, row.key, caches['subjects'])
    if row.subject.kind == 'elective_slot':
        row.errors.append('Un hueco de optativa no se califica; indica la optativa cursada.')
    if row.slot_key and row.subject.kind != 'elective':
        row.errors.append('La columna hueco sólo aplica a optativas.')

    if row.period_code not in caches['periods']:
        caches['periods'][row.period_code] = AcademicPeriod.query.filter_by(
            code=row.period_code).first()
    row.period = caches['periods'][row.period_code]
    if row.period is None:
        row.errors.append('El periodo no existe.')
    elif row.period.is_active or row.period.end_date >= today:
        row.errors.append('Sólo se importan periodos ya concluidos.')

    try:
        row.value = parse_value(row.raw_value)
    except DomainError as e:
        row.errors.append(str(e))


# ── Per-student ordering rules ───────────────────────────────────────────────

def _existing(up_id: int) -> list[CourseEnrollment]:
    """Every recorded row, dropped ones included (they still hold the unique key)."""
    return (CourseEnrollment.query.join(AcademicPeriod,
                                        AcademicPeriod.id == CourseEnrollment.academic_period_id)
            .filter(CourseEnrollment.user_program_id == up_id)
            .all())


def _validate_student(up: UserProgram, rows: list[Row]) -> None:
    """Attempt numbers, order against recorded attempts, duplicates and slots."""
    taken = defaultdict(list)   # subject_id -> [(start_date, period_id, result, slot_id)]
    dropped = set()             # (subject_id, period_id) of dropped rows
    for e in _existing(up.id):
        if e.status == 'dropped':
            dropped.add((e.subject_id, e.academic_period_id))
            continue
        taken[e.subject_id].append((e.academic_period.start_date, e.academic_period_id,
                                    e.result, e.slot_subject_id))
    plan_slots = [s for s in Subject.query.filter_by(plan_id=up.curriculum_plan_id,
                                                     kind='elective_slot')
                  .order_by(Subject.suggested_semester.nullslast(), Subject.sequence,
                            Subject.id).all()]
    used_slots = {slot for attempts in taken.values() for *_, slot in attempts if slot}

    blocked = {}                # subject_id -> line of an earlier rejected row
    for row in sorted(rows, key=lambda r: (r.period.start_date, r.line)):
        _check_order(row, taken, dropped, blocked, plan_slots, used_slots)
        if row.errors:
            blocked.setdefault(row.subject.id, row.line)


def _check_order(row: Row, taken, dropped, blocked, plan_slots, used_slots) -> None:
    """Place one row after the student's earlier attempts; append it when valid."""
    history = taken[row.subject.id]
    if row.subject.id in blocked:
        row.errors.append(f'Corrige primero la fila {blocked[row.subject.id]} de esta materia.')
        return
    if (row.subject.id, row.period.id) in dropped:
        row.errors.append('La materia figura como baja en ese periodo.')
        return
    if any(pid == row.period.id for _, pid, _, _ in history):
        row.errors.append('Ya hay un registro de esa materia en ese periodo.')
        return
    if any(start >= row.period.start_date for start, *_ in history):
        row.errors.append('Ya hay un intento registrado en un periodo igual o posterior.')
        return
    if any(result == 'passed' for _, _, result, _ in history):
        row.errors.append('La materia ya está aprobada en un periodo anterior.')
        return
    attempt = len(history) + 1
    if attempt > MAX_ATTEMPTS:
        row.errors.append('Excede los tres intentos de la materia.')
        return

    slot = None
    if row.subject.kind == 'elective':
        earlier = next((s for *_, s in history if s), None)
        if earlier is not None:
            slot = next((s for s in plan_slots if s.id == earlier), None)
        elif row.slot_key:
            slot = next((s for s in plan_slots if (s.key or '').upper() == row.slot_key), None)
            if slot is None:
                row.errors.append('El hueco no existe en el plan del alumno.')
                return
            if slot.id in used_slots:
                row.errors.append('Ese hueco de optativa ya está cubierto.')
                return
        else:
            slot = next((s for s in plan_slots if s.id not in used_slots), None)
            if slot is None:
                row.errors.append('El alumno ya cubrió todas sus optativas.')
                return
        used_slots.add(slot.id)

    row.attempt, row.slot = attempt, slot
    history.append((row.period.start_date, row.period.id, row.result,
                    slot.id if slot else None))


def _validate(text: str, program_ids: Optional[set]) -> list[Row]:
    rows = parse_csv(text)
    scope = program_ids
    today = now_local().date()
    caches = {'subjects': {}, 'periods': {}}
    for row in rows:
        _resolve(row, scope, today, caches)
    by_student = defaultdict(list)
    for row in rows:
        if row.valid:
            by_student[row.up.id].append(row)
    for student_rows in by_student.values():
        _validate_student(student_rows[0].up, student_rows)
    return rows


def _summary(rows: list[Row]) -> dict:
    valid = [r for r in rows if r.valid]
    return {
        'rows': [r.as_dict() for r in rows],
        'valid_count': len(valid),
        'error_count': len(rows) - len(valid),
        'student_count': len({r.up.id for r in valid}),
        'special_failed_count': sum(1 for r in valid if r.special_failed),
    }


# ── Public API ───────────────────────────────────────────────────────────────

def preview(text: str, program_ids: Optional[set]) -> dict:
    """
    Validate the CSV and describe every row; writes nothing.

    `program_ids` follows `program_scope_service.accessible_program_ids`:
    None = every program, set() = none.
    """
    return _summary(_validate(text, program_ids))


def _lock(up_id: int) -> Optional[UserProgram]:
    return (UserProgram.query.filter_by(id=up_id)
            .with_for_update().populate_existing().first())


def _notify_special_failed(up: UserProgram, rows: list[Row]) -> None:
    coordinator_id = up.program.coordinator_id if up.program else None
    if not coordinator_id:
        return
    user = up.user
    subjects = ', '.join(r.subject.name for r in rows)
    NotificationService.create_notification(
        user_id=coordinator_id, notification_type='grade_import_special_failed',
        title='Historial importado: especial reprobado',
        message=(f'{user.first_name} {user.last_name} tiene un especial reprobado en su '
                 f'historial ({subjects}). Revisa si procede la baja.'),
        priority='high', action_url=f'/students/{user.uuid}/record?tab=trayectoria',
    )


def _write_student(up_id: int, student_rows: list[Row], actor_id: int,
                   program_ids: Optional[set]) -> bool:
    """Re-check one student under its row lock and add its rows. True = flag for review."""
    up = _lock(up_id)
    if (up is None or up.admission_status != 'enrolled'
            or (program_ids is not None and up.program_id not in program_ids)):
        for row in student_rows:
            row.errors[:] = [NOT_FOUND]
        return False
    for row in student_rows:   # fresh rules under the lock: a concurrent write may exist
        row.errors.clear()
        row.up = up
        row.attempt = row.slot = None
        row.subject = db.session.get(Subject, row.subject.id)
        row.period = db.session.get(AcademicPeriod, row.period.id)
    _validate_student(up, student_rows)
    ok = [r for r in student_rows if r.valid]
    if not ok:
        return False
    stamp = now_local()
    for r in ok:
        db.session.add(CourseEnrollment(
            user_program_id=up.id, subject_id=r.subject.id, academic_period_id=r.period.id,
            slot_subject_id=r.slot.id if r.slot else None, course_group_id=None,
            attempt=r.attempt, attempt_type=r.attempt_type, status='graded',
            grade=r.value[0], grade_mark=r.value[1], result=r.result,
            graded_at=stamp, graded_by=actor_id, created_by=actor_id))
    UserHistoryService.log_action(
        user_id=up.user_id, action='grade_imported', admin_id=actor_id,
        user_program_id=up.id,
        details={'count': len(ok), 'rows': [
            {'subject': r.subject.name, 'period': r.period.code,
             'value': display(*r.value), 'attempt': r.attempt_type} for r in ok]},
    )
    specials = [r for r in ok if r.special_failed]
    flag = bool(specials) and up.academic_status in (None, 'active', 'on_leave')
    if flag:
        _notify_special_failed(up, specials)
    return flag


def execute(text: str, actor_id: int, program_ids: Optional[set]) -> dict:
    """Write the valid rows, one transaction per student. Returns the summary."""
    rows = _validate(text, program_ids)
    by_student = defaultdict(list)
    for row in rows:
        if row.valid:
            by_student[row.up.id].append(row)

    flagged = []
    for up_id, student_rows in by_student.items():
        try:
            flag = _write_student(up_id, student_rows, actor_id, program_ids)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            message = 'Otro proceso registró calificaciones de este alumno; vuelve a cargar el archivo.'
        except Exception:   # one student never sinks the rest
            db.session.rollback()
            logger.exception('[history_import] student up_id=%s failed', up_id)
            message = 'No se pudo importar este alumno; inténtalo de nuevo.'
        else:
            if flag:
                user = student_rows[0].up.user
                flagged.append(f'{user.first_name} {user.last_name}')
            continue
        for r in student_rows:
            if r.valid:
                r.errors.append(message)

    summary = _summary(rows)
    summary['flagged_students'] = flagged
    return summary

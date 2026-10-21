"""
Coordinator service — data access and rules behind the coordinator panels.

Backs `app/routes/api/coordinator_api.py` and `app/routes/pages/coordinator_pages.py`.
Framework-agnostic: no `request`, no `g`, no `current_user`. Callers pass the
viewer (a User) or a resolved scope explicitly.

Scope reminder: `scope` is the value of
`program_scope_service.accessible_program_ids(viewer)` — `None` means global,
an empty set means "no programs".
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import and_, or_, select

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.appointment import Appointment
from app.models.archive import Archive
from app.models.event import Event, EventSlot, EventWindow
from app.models.phase import Phase
from app.models.program import Program
from app.models.program_step import ProgramStep
from app.models.semester_enrollment import SemesterEnrollment
from app.models.step import Step
from app.models.submission import Submission
from app.models.user import User
from app.models.user_program import UserProgram
from app.services import program_scope_service as scope_service
from app.services.errors import DomainError
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local
from app.utils.files import save_user_doc

logger = logging.getLogger(__name__)


# ─── Program / enrollment lookups ────────────────────────────────────────────

def get_program(program_id: int) -> Optional[Program]:
    """Program by internal id, or None."""
    return db.session.get(Program, program_id)


def get_program_or_404(program_id: int) -> Program:
    """Program by internal id; aborts with the framework 404 when missing."""
    return Program.query.get_or_404(program_id)


def first_user_program(student_id: int) -> Optional[UserProgram]:
    """Any UserProgram of the student (no scope applied), or None."""
    return UserProgram.query.filter_by(user_id=student_id).first()


def scoped_user_program(viewer, student_id: int) -> Optional[UserProgram]:
    """
    UserProgram of the student that falls INSIDE the viewer's scope.

    A student may hold several UserProgram rows (program change). Taking
    `.first()` blindly let a coordinator write on an enrollment of a program
    outside their reach just because they shared another one with the student.

    Returns None when the student has none that the viewer can reach.
    """
    rows = UserProgram.query.filter_by(user_id=student_id).all()
    if not rows:
        return None
    scope = scope_service.accessible_program_ids(viewer)
    if scope is None:
        return rows[0]
    for up in rows:
        if up.program_id in scope:
            return up
    return None


def accessible_programs(pids) -> list:
    """Programs visible for a scope: all when `pids` is None, none when empty."""
    if pids is None:
        return Program.query.order_by(Program.name).all()
    if not pids:
        return []
    return Program.query.filter(Program.id.in_(pids)).order_by(Program.name).all()


def list_programs_in_scope(scope) -> list:
    """Programs (unordered, as the API always returned them) for a scope."""
    if scope is None:
        return Program.query.all()
    if not scope:
        return []
    return Program.query.filter(Program.id.in_(scope)).all()


def permanence_page_context() -> dict:
    """Active period, all periods and phase-2 archives for the permanence page."""
    active_period = AcademicPeriod.get_active_period()
    all_periods = AcademicPeriod.query.order_by(AcademicPeriod.start_date.desc()).all()
    # Active archives of the permanence phase (phase_id=2) for the "Nueva Ventana" modal.
    permanence_archives = (
        Archive.query
        .join(Step, Archive.step_id == Step.id)
        .filter(Step.phase_id == 2, Archive.is_active == True)  # noqa: E712
        .order_by(Step.id, Archive.name)
        .all()
    )
    return {
        'active_period': active_period,
        'all_periods': all_periods,
        'permanence_archives': permanence_archives,
    }


# ─── Student panels ──────────────────────────────────────────────────────────

def list_panel_rows(scope, *, show_other: bool, program_id: Optional[int],
                    search: str) -> list:
    """
    (User, UserProgram, Program) rows of the coordinator panel.

    The `is_active` filter defines the panel population (active accounts),
    identical for every caller, so it cannot act as a comparative oracle. The
    search only touches fields the cross-program summary may expose.
    """
    query = db.session.query(User, UserProgram, Program).join(
        UserProgram, User.id == UserProgram.user_id
    ).join(
        Program, UserProgram.program_id == Program.id
    ).filter(
        User.role.has(name='applicant') | User.role.has(name='student'),
        User.is_active == True,  # noqa: E712
    )

    if scope is not None and not show_other:
        if not scope:
            return []
        query = query.filter(Program.id.in_(scope))

    if program_id:
        query = query.filter(Program.id == program_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(*[
                getattr(User, field).ilike(search_term)
                for field in sorted(scope_service.CROSS_PROGRAM_SEARCHABLE_FIELDS)
            ])
        )
    return query.all()


def list_manageable_applicants(scope) -> list:
    """(User, Program) rows of active applicants inside `scope` (None = all)."""
    program_filter = True if scope is None else Program.id.in_(scope)
    return db.session.query(User, Program).join(
        UserProgram, User.id == UserProgram.user_id
    ).join(
        Program, UserProgram.program_id == Program.id
    ).filter(
        User.role.has(name='applicant'),
        User.is_active == True,  # noqa: E712
        program_filter,
    ).order_by(User.first_name, User.last_name).all()


def uploadable_archives_for(student_id: int, program_id: int) -> list:
    """
    Archives a coordinator may upload for the student, with the current
    submission (if any): list of (archive, step, phase, existing_submission).
    """
    query = db.session.query(Archive, Step, Phase).join(
        Step, Archive.step_id == Step.id
    ).join(
        Phase, Step.phase_id == Phase.id
    ).join(
        ProgramStep, and_(
            ProgramStep.step_id == Step.id,
            ProgramStep.program_id == program_id,
        )
    ).filter(
        Archive.allow_coordinator_upload == True,  # noqa: E712
        Archive.is_uploadable == True,  # noqa: E712
    ).order_by(Phase.id, ProgramStep.sequence)

    rows = []
    for archive, step, phase in query:
        existing = Submission.query.filter_by(
            user_id=student_id, archive_id=archive.id
        ).first()
        rows.append((archive, step, phase, existing))
    return rows


def get_archive(archive_id: int) -> Optional[Archive]:
    """Archive by internal id, or None."""
    return db.session.get(Archive, archive_id)


def upload_for_student(*, student_id: int, user_program: UserProgram,
                       archive: Archive, file, decision: str, notes: str,
                       uploader_id: int) -> Submission:
    """
    Record a coordinator-side submission (with or without a file) for a student.

    Replaces any previous submission of the same archive. Raises DomainError
    when the program is missing the step, and re-raises unexpected errors after
    rolling back so the caller can answer 500.
    """
    try:
        # With a file it is stored; without one file_path stays None.
        file_relative_path = None
        if file:
            file_relative_path = save_user_doc(
                file_storage=file,
                user_id=student_id,
                phase='admission',
                name=archive.name,
            )

        program_step = ProgramStep.query.filter_by(
            program_id=user_program.program_id,
            step_id=archive.step_id,
        ).first()
        if not program_step:
            raise DomainError("Configuración de programa incompleta")

        existing = Submission.query.filter_by(
            user_id=student_id, archive_id=archive.id
        ).first()
        if existing:
            db.session.delete(existing)

        new_status = 'approved' if decision == 'approve' else 'rejected'
        prefix = '[Coordinador]'
        if not file:
            prefix = '[Coordinador · validación sin archivo]'
        comment_body = notes if notes else (
            'Documento subido y aprobado' if decision == 'approve' else 'Documento rechazado'
        )

        submission = Submission(
            file_path=file_relative_path,
            status=new_status,
            review_date=now_local(),
            reviewer_comment=f"{prefix} {comment_body}",
            user_id=student_id,
            archive_id=archive.id,
            program_step_id=program_step.id,
            semester=None,
            uploaded_by=uploader_id,
            uploaded_by_role='program_admin',
            user_program_id=user_program.id,
        )
        submission.reviewer_id = uploader_id

        db.session.add(submission)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    try:
        UserHistoryService.log_document_upload(
            user_id=student_id,
            archive_name=archive.name,
            program_name=user_program.program.name,
            uploaded_by_admin=True,
            admin_id=uploader_id,
        )
        db.session.commit()
    except Exception as e:  # history must never fail the upload
        logger.error(f"Error al registrar subida por coordinador en historial: {e}")
    return submission


def permanence_enrollment_context(user_program: UserProgram) -> tuple:
    """(active_period, current_enrollment, semester_history) for the modal."""
    active_period = AcademicPeriod.get_active_period()
    current_enrollment = None
    if active_period:
        current_enrollment = SemesterEnrollment.query.filter_by(
            user_program_id=user_program.id,
            academic_period_id=active_period.id,
        ).first()
    history = SemesterEnrollment.query.filter_by(
        user_program_id=user_program.id
    ).order_by(SemesterEnrollment.semester_number.asc()).all()
    return active_period, current_enrollment, history


def get_active_period_id() -> Optional[int]:
    """Id of the active academic period, or None."""
    period = AcademicPeriod.get_active_period()
    return period.id if period else None


def get_interview_status(student_id: int, program_id: int) -> dict:
    """Interview appointment summary of the student (any non-cancelled one)."""
    appointment = db.session.execute(
        select(Appointment)
        .join(EventSlot, Appointment.slot_id == EventSlot.id)
        .join(EventWindow, EventSlot.event_window_id == EventWindow.id)
        .join(Event, EventWindow.event_id == Event.id)
        .where(
            Appointment.applicant_id == student_id,
            Appointment.status.in_(['scheduled', 'done', 'no_show']),
            or_(Event.program_id == program_id, Event.program_id.is_(None)),
            Event.type == 'interview',
        )
    ).scalar_one_or_none()

    if not appointment:
        return {"has_interview": False, "appointment": None}

    slot = db.session.get(EventSlot, appointment.slot_id)
    window = db.session.get(EventWindow, slot.event_window_id)
    event = db.session.get(Event, window.event_id)

    return {
        "has_interview": True,
        "appointment": {
            "id": appointment.id,
            "status": appointment.status,
            "notes": appointment.notes,
            "created_at": appointment.created_at.isoformat(),
            "event": {
                "id": event.id,
                "title": event.title,
                "location": event.location,
                "description": event.description,
            },
            "slot": {
                "starts_at": slot.starts_at.isoformat(),
                "ends_at": slot.ends_at.isoformat(),
            },
        },
    }


def compute_permanence_metrics(user_program, program, active_period_id) -> dict:
    """
    Real permanence metrics for a UserProgram.

    Keys: current_semester, completed_semesters, total_semesters (program
    duration, default 4), academic_progress (% completed), in_progress_segment
    (% of the running semester, only with an 'active' enrollment in the active
    period) and academic_status ('active' | 'on_leave' | 'completed' |
    'dropped' | 'pending').
    """
    total = max(int(program.duration_semesters or 4), 1)
    current_semester = user_program.current_semester or 1

    completed = (
        SemesterEnrollment.query
        .filter_by(user_program_id=user_program.id, status='completed')
        .count()
    )
    completed = min(completed, total)

    current_enrollment = None
    if active_period_id is not None:
        current_enrollment = (
            SemesterEnrollment.query
            .filter_by(user_program_id=user_program.id, academic_period_id=active_period_id)
            .first()
        )

    if current_enrollment is not None:
        academic_status = current_enrollment.status
    elif completed >= total:
        academic_status = 'completed'
    else:
        academic_status = 'pending'

    progress_pct = round((completed / total) * 100, 2)
    segment_pct = round((1 / total) * 100, 2)

    in_progress_segment = 0
    if academic_status == 'active' and (progress_pct + segment_pct) <= 100.001:
        in_progress_segment = segment_pct

    return {
        "current_semester": current_semester,
        "completed_semesters": completed,
        "total_semesters": total,
        "academic_progress": progress_pct,
        "in_progress_segment": in_progress_segment,
        "academic_status": academic_status,
    }

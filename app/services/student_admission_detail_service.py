"""
Admission detail of one student, for the coordinator's student record.

This is the data the old dashboard modal showed (document checklist per step,
metrics, missing documents, interview eligibility), moved out of the API route
so the JSON endpoint and the record page's HTML fragment share one builder.

Scope is NOT decided here: callers resolve it first (`scoped_user_program` for
the full detail, `get_cross_program_summary` for the reduced tier).
"""
from typing import Optional

from app.models.user import User
from app.services import coordinator_service
from app.services import file_access_service
from app.services import program_scope_service as scope_service
from app.services.admission_service import get_admission_state
from app.services.interview_service import InterviewEligibilityService


def is_student_account(user) -> bool:
    """Only applicants and students are targets of the coordination panels."""
    return getattr(getattr(user, 'role', None), 'name', None) in ('applicant', 'student')


def format_archive_status(archive, subs, all_extensions) -> dict:
    """State of one archive (submission, extension, upload permissions)."""
    sub = subs.get(archive.id)
    ext = all_extensions.get(archive.id)
    return {
        # Public handle: the browser posts it back as `archive_id`.
        "id": str(archive.uuid) if archive.uuid else None,
        "name": archive.name,
        "description": archive.description,
        "has_submission": bool(sub),
        "status": sub.status if sub else "pending",
        "uploaded_at": sub.upload_date.isoformat() if sub and sub.upload_date else None,
        "uploaded_by_role": sub.uploaded_by_role if sub else None,
        "reviewer_comment": sub.reviewer_comment if sub else None,
        "review_date": sub.review_date.isoformat() if sub and sub.review_date else None,
        # Opaque URL: it names the row, never the student's integer id.
        "file_url": file_access_service.submission_file_url(sub),
        "has_extension": bool(ext),
        "extension_status": ext.status if ext else None,
        "extension_until": ext.granted_until.isoformat() if ext and ext.granted_until else None,
        "is_uploadable": archive.is_uploadable,
        "allow_coordinator_upload": archive.allow_coordinator_upload,
    }


def missing_documents(documents_by_step: list) -> list:
    """Pending or rejected archives, flattened."""
    missing = []
    for step in documents_by_step:
        for arch in step['archives']:
            if arch['status'] in ('pending', 'rejected'):
                missing.append({
                    "step": step['step_name'],
                    "archive": arch['name'],
                    "status": arch['status'],
                })
    return missing


def documents_by_step(admission_state: dict) -> list:
    """Archives of every admission step (sequence 0 excluded) with their status."""
    out = []
    subs = admission_state['subs']
    extensions = admission_state['all_extensions']
    for item in admission_state['processed_steps']:
        if item['sequence'] == 0:
            continue
        if item['is_combined']:
            step_data = {
                "step_id": item['id'],
                "step_name": item['name'],
                "sequence": item['sequence'],
                "is_combined": True,
                "locked": item['locked'],
                "state": item['state'],
                "archives": [],
            }
            for part in ('step1', 'step2'):
                for arch in item[part].archives:
                    step_data['archives'].append(format_archive_status(arch, subs, extensions))
        else:
            step = item['step']
            step_data = {
                "step_id": step.id,
                "step_name": step.name,
                "sequence": item['sequence'],
                "is_combined": False,
                "locked": item['locked'],
                "state": item['state'],
                "archives": [
                    format_archive_status(arch, subs, extensions) for arch in step.archives
                ],
            }
        out.append(step_data)
    return out


def build_admission_detail(student: User, user_program, program) -> dict:
    """
    Full admission detail: documents per step, interview, metrics and missing
    documents. Only for a student INSIDE the caller's scope.
    """
    admission_state = get_admission_state(student.id, program.id, user_program)
    steps = documents_by_step(admission_state)
    counts = admission_state['status_count']
    interview_status = coordinator_service.get_interview_status(student.id, program.id)
    eligibility = InterviewEligibilityService.check_student_eligibility(student.id, program.id)
    return {
        "documents": steps,
        "interview": {**interview_status, "eligibility": eligibility},
        "metrics": {
            "total_documents": len([a for step in steps for a in step['archives']]),
            "approved": counts.get('approved', 0),
            "pending": counts.get('pending', 0),
            "rejected": counts.get('rejected', 0),
            "extended": counts.get('extended', 0),
            "in_review": counts.get('review', 0),
            "progress_percentage": admission_state['progress_pct'],
        },
        "missing_documents": missing_documents(steps),
    }


def get_cross_program_summary(viewer, student: User) -> Optional[dict]:
    """
    Reduced tier (name, e-mail, progress/status) of a student OUTSIDE the
    viewer's scope, or None when the viewer may not see even that.

    None covers: viewer without the tier permission, target that is not an
    applicant/student account, and target without any program enrolment. The
    caller answers all of them with the same 404.
    """
    if not scope_service.may_view_cross_program_summary(viewer):
        return None
    if not is_student_account(student):
        return None
    user_program = coordinator_service.first_user_program(student.id)
    if user_program is None:
        return None
    program = coordinator_service.get_program(user_program.program_id)
    admission_state = get_admission_state(student.id, program.id, user_program)
    counts = admission_state.get('status_count', {})
    flat = {
        "id": str(student.uuid) if student.uuid else None,
        "full_name": f"{student.first_name} {student.last_name} {student.mother_last_name or ''}".strip(),
        "email": student.email,
        "program_id": program.id,
        "program_name": program.name,
        "program_slug": program.slug,
        "can_manage": False,
        "admission_status": user_program.admission_status,
        "current_semester": user_program.current_semester or 1,
        "progress_percentage": admission_state.get('progress_pct', 0),
        "approved_docs": counts.get('approved', 0),
        "pending_docs": counts.get('pending', 0),
        "rejected_docs": counts.get('rejected', 0),
        "extended_docs": admission_state.get('extended_docs', 0),
    }
    return scope_service.to_cross_program_summary(flat)


# ─── Record page: fragment context and coordinator upload ────────────────────

MAX_COORDINATOR_UPLOAD_BYTES = 3 * 1024 * 1024


def admission_context(viewer, student: User) -> dict:
    """
    Context of the admission fragment for a student the caller already passed
    the record scope check for.

    `detail` is None when the student has no enrolment inside the viewer's
    scope (a staff account, or the viewer looking at themselves): the partial
    renders an empty state instead of a checklist.
    """
    user_program = coordinator_service.scoped_user_program(viewer, student.id)
    if user_program is None:
        return {"detail": None, "program": None}
    program = coordinator_service.get_program(user_program.program_id)
    return {
        "detail": build_admission_detail(student, user_program, program),
        "program": program,
    }


def upload_admission_document(viewer, student: User, *, archive_uuid, file,
                              decision: str, notes: str) -> str:
    """
    Register a coordinator-side submission for `student`. Returns the user message.

    The caller already passed the record scope check; the write still resolves
    the enrolment INSIDE the viewer's scope (a student with two programs is
    never written through the one the viewer does not manage).

    Raises NotFoundError / DomainError, rendered by the app-level handlers.
    """
    from app.models.archive import Archive
    from app.services.errors import DomainError, NotFoundError

    if not is_student_account(student):
        raise NotFoundError("Estudiante no encontrado")

    archive = Archive.by_uuid(archive_uuid) if archive_uuid else None
    if archive is None:
        raise NotFoundError("Archivo no encontrado")

    if file is not None and not getattr(file, 'filename', ''):
        file = None
    if not file and not notes:
        raise DomainError(
            "Si no subes un archivo debes proporcionar al menos un comentario justificativo."
        )
    if file:
        if not file.filename.lower().endswith('.pdf'):
            raise DomainError("Solo se permiten archivos PDF.")
        file.stream.seek(0, 2)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > MAX_COORDINATOR_UPLOAD_BYTES:
            raise DomainError("El archivo no puede superar los 3 MB.")

    user_program = coordinator_service.scoped_user_program(viewer, student.id)
    if user_program is None:
        raise NotFoundError("Estudiante no inscrito")
    if not archive.allow_coordinator_upload:
        raise DomainError("Este archivo no permite subida por coordinador.")

    coordinator_service.upload_for_student(
        student_id=student.id,
        user_program=user_program,
        archive=archive,
        file=file,
        decision=decision,
        notes=notes,
        uploader_id=viewer.id,
    )
    return (
        f"Documento {'aprobado' if decision == 'approve' else 'rechazado'} exitosamente"
        + ('' if file else ' (sin archivo adjunto)')
        + "."
    )

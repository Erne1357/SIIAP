"""
Phase 6C — conclusion: thesis and its committees, admission conditions,
conclusion requirements, the grade exam and titling.

Flow fixed by the owner (2026-10-22, PLAN_FASE6C_diseno.md):
- The thesis and its tutorial committee are registered from `active` on.
- Conclusion requirements (Submission, phase 'conclusion') open once the
  student is `graduated`. Documents the institution issues
  (`Archive.issued_by_institution`) are uploaded by the coordination.
- An approved admission document (previous degree, English) satisfies the
  equivalent conclusion requirement (`REUSE`), unless a pending admission
  condition points at that requirement or the student already has an own
  conclusion submission for it (that one always wins, whatever its status).
- Approving (review inbox) the requirement a pending condition points at
  marks that condition met (`on_requirement_approved`); a condition created
  against a requirement already satisfied is born met.
- Reuse honours the admission archive's `validity_months`: a lapsed document
  is 'reused_expired' (not satisfied) unless the coordination accepted it
  (override 'accept_expired'); the student may upload a fresh one instead.
- The coordination may mark a requirement 'not_applicable' for one student
  (override, reason mandatory, reversible); it then counts as satisfied.
- Titled / withdrawn files are read-only (no thesis, member, condition or
  override changes).
- Scheduling the exam needs `graduated` + every requirement satisfied +
  every condition met/waived + a board with president, secretary and vocal.
  An approved exam moves `academic_status` to `titled`; only a
  `postgraduate_admin` reverts it, with a reason.

Scope: every actor-based function checks `program_in_scope(actor, ...)`
and answers an unknown or out-of-scope target with the same NotFoundError.
Framework-agnostic: callers pass the acting `User` (or ids) explicitly.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy import or_

from app import db
from app.models import Archive, Phase, ProgramStep, Step, Submission, User, UserProgram
from app.models.admission_condition import AdmissionCondition
from app.models.conclusion_requirement_override import (
    OVERRIDE_KINDS, ConclusionRequirementOverride,
)
from app.models.grade_exam import EXAM_VERDICTS, GradeExam
from app.models.thesis import MEMBER_ROLES, Thesis, ThesisMember
from app.services import academic_status_service as status_svc
from app.services import program_scope_service as scope_service
from app.services.errors import ConflictError, DomainError, NotFoundError
from app.services.notification_service import NotificationService
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local, to_local_timezone

logger = logging.getLogger(__name__)

CONCLUSION_PHASE = 'conclusion'

#: conclusion archive_key -> admission archive_keys that satisfy it, most
#: specific first (a doctorate's previous degree is the master's title).
REUSE = {
    'conclusion_previous_degree': ('admission_degree_title_phd', 'admission_degree_title_ms'),
    'conclusion_second_language': ('admission_english_phd', 'admission_english_ms'),
}

#: Statuses in which a thesis may be registered or edited.
THESIS_STATUSES = frozenset({status_svc.ACTIVE, status_svc.ON_LEAVE, status_svc.GRADUATED})

#: Board roles an exam needs before it can be scheduled.
REQUIRED_EXAM_ROLES = ('president', 'secretary', 'vocal')

#: Requirement statuses that count as fulfilled.
SATISFIED_STATUSES = frozenset({'approved', 'reused', 'institution_done', 'not_applicable'})

#: Academic statuses in which the conclusion file is read-only.
READ_ONLY_STATUSES = frozenset({status_svc.TITLED, status_svc.WITHDRAWN})

#: Note shown on a reused document whose lapsed validity the coordination accepted.
EXPIRED_ACCEPTED_NOTE = 'Vigencia vencida aceptada por la coordinación'

OVERRIDE_LABELS_ES = {'not_applicable': 'No aplica',
                      'accept_expired': 'Vigencia vencida aceptada'}

ROLE_LABELS_ES = {
    'director': 'director(a)',
    'codirector': 'codirector(a)',
    'advisor': 'asesor(a)',
    'president': 'presidente(a)',
    'secretary': 'secretario(a)',
    'vocal': 'vocal',
    'substitute': 'suplente',
}
BODY_LABELS_ES = {'tutorial': 'comité tutorial', 'exam': 'sínodo'}

STAGE_LABELS_ES = {
    'not_started': 'Inicial',
    'thesis': 'Tesis registrada',
    'requirements': 'Requisitos',
    'ready': 'Lista para examen',
    'exam_scheduled': 'Examen agendado',
    'titled': 'Titulado',
    'closed': 'Sin conclusión',
}

STUDENT_NOT_FOUND_MESSAGE = 'Estudiante no encontrado.'
EXAM_NOT_FOUND_MESSAGE = 'Examen no encontrado.'
CONDITION_NOT_FOUND_MESSAGE = 'Condición no encontrada.'
MEMBER_NOT_FOUND_MESSAGE = 'Integrante no encontrado.'
ARCHIVE_NOT_FOUND_MESSAGE = 'Documento no encontrado.'


class ConclusionError(DomainError):
    """Base of the business errors of this module."""


class ConclusionNotFound(ConclusionError, NotFoundError):
    """Unknown target, or one outside the caller's program scope."""


class ConclusionConflict(ConclusionError, ConflictError):
    """The operation clashes with the current state (409)."""


# ─── Lookups ─────────────────────────────────────────────────────────────────

def effective_status(up: UserProgram) -> Optional[str]:
    """`academic_status`, counting an enrolled row the backfill missed as active."""
    if up.academic_status is None and up.admission_status == 'enrolled':
        return status_svc.ACTIVE
    return up.academic_status


def is_read_only(up: UserProgram) -> bool:
    """Titled or withdrawn: the conclusion file only shows, nothing changes."""
    return effective_status(up) in READ_ONLY_STATUSES


def _require_writable(up: UserProgram, what: str) -> None:
    if is_read_only(up):
        label = status_svc.STATUS_LABELS_ES.get(up.academic_status, up.academic_status)
        raise ConclusionError(f'No se pueden {what} con estado académico "{label}".')


def _in_scope(actor, up: Optional[UserProgram]) -> bool:
    return up is not None and scope_service.program_in_scope(actor, up.program_id)


def get_user_program(actor, user_program_id: int) -> UserProgram:
    """The student program, if the actor's scope reaches it (else 404)."""
    up = db.session.get(UserProgram, user_program_id) if user_program_id else None
    if not _in_scope(actor, up):
        raise ConclusionNotFound(STUDENT_NOT_FOUND_MESSAGE)
    return up


def _locked(actor, user_program_id: int) -> UserProgram:
    """Scope check, then `SELECT ... FOR UPDATE` refreshing the row."""
    get_user_program(actor, user_program_id)
    up = (UserProgram.query.filter_by(id=user_program_id)
          .with_for_update().populate_existing().first())
    if up is None:
        raise ConclusionNotFound(STUDENT_NOT_FOUND_MESSAGE)
    return up


def get_thesis(up: UserProgram) -> Optional[Thesis]:
    return Thesis.query.filter_by(user_program_id=up.id).first()


def conditions(up: UserProgram) -> list:
    return (AdmissionCondition.query.filter_by(user_program_id=up.id)
            .order_by(AdmissionCondition.created_at, AdmissionCondition.id).all())


def exams(up: UserProgram) -> list:
    """Every exam of the student program, newest first."""
    return (GradeExam.query.filter_by(user_program_id=up.id)
            .order_by(GradeExam.scheduled_at.desc(), GradeExam.id.desc()).all())


def current_exam(up: UserProgram) -> Optional[GradeExam]:
    """The scheduled exam, if any."""
    return GradeExam.query.filter_by(user_program_id=up.id, status='scheduled').first()


def conclusion_archives(program_id: int) -> list:
    """(ProgramStep, Archive) of the program's conclusion phase, in step order."""
    rows = (
        db.session.query(ProgramStep, Archive)
        .join(Step, ProgramStep.step_id == Step.id)
        .join(Phase, Step.phase_id == Phase.id)
        .join(Archive, Archive.step_id == Step.id)
        .filter(ProgramStep.program_id == program_id,
                Phase.name == CONCLUSION_PHASE,
                Archive.is_active.is_(True))
        .order_by(ProgramStep.sequence, ProgramStep.id, Archive.id)
        .all()
    )
    return rows


def archive_by_key(key: Optional[str]) -> Optional[Archive]:
    if not key:
        return None
    return Archive.query.filter_by(archive_key=key).first()


def _program_archive(up: UserProgram, archive_uuid) -> tuple:
    """(ProgramStep, Archive) of a conclusion archive of the student's program, else 404."""
    archive = Archive.by_uuid(archive_uuid) if not isinstance(archive_uuid, Archive) else archive_uuid
    if archive is not None:
        for ps, candidate in conclusion_archives(up.program_id):
            if candidate.id == archive.id:
                return ps, candidate
    raise ConclusionNotFound(ARCHIVE_NOT_FOUND_MESSAGE)


def _latest_submission(up: UserProgram, archive_id: int) -> Optional[Submission]:
    """The newest submission of an archive for this student program."""
    return (
        Submission.query
        .outerjoin(ProgramStep, Submission.program_step_id == ProgramStep.id)
        .filter(Submission.archive_id == archive_id,
                or_(Submission.user_program_id == up.id,
                    (Submission.user_id == up.user_id)
                    & (ProgramStep.program_id == up.program_id)))
        .order_by(Submission.upload_date.desc(), Submission.id.desc())
        .first()
    )


def _approved_submission(up: UserProgram, archive_id: int) -> Optional[Submission]:
    return (
        Submission.query
        .outerjoin(ProgramStep, Submission.program_step_id == ProgramStep.id)
        .filter(Submission.archive_id == archive_id,
                Submission.status == 'approved',
                or_(Submission.user_program_id == up.id,
                    (Submission.user_id == up.user_id)
                    & (ProgramStep.program_id == up.program_id)))
        .order_by(Submission.upload_date.desc(), Submission.id.desc())
        .first()
    )


def _reuse_source(up: UserProgram, archive: Archive, blocked_ids: set) -> Optional[Submission]:
    """
    Approved admission submission that satisfies `archive`, or None.

    The candidate is the most specific admission archive the student's
    program actually asks for (a doctorate asks for both the master's-level
    and the doctorate-level title; only the latter is its previous degree).
    """
    keys = REUSE.get(archive.archive_key or '')
    if not keys or archive.id in blocked_ids:
        return None
    candidates = Archive.query.filter(Archive.archive_key.in_(keys)).all()
    by_key = {a.archive_key: a for a in candidates}
    ordered = [by_key[k] for k in keys if k in by_key]
    if not ordered:
        return None
    program_step_ids = {ps.step_id for ps in
                        ProgramStep.query.filter_by(program_id=up.program_id).all()}
    linked = [a for a in ordered if a.step_id in program_step_ids]
    source = (linked or ordered)[0]
    return _approved_submission(up, source.id)


# ─── Requirements ────────────────────────────────────────────────────────────

def reuse_expires_at(sub: Optional[Submission]) -> Optional[datetime]:
    """When a reusable admission submission lapses (its archive's
    `validity_months` from `upload_date`), or None if it never does."""
    from app.services.admission_service import _add_months

    archive = sub.archive if sub is not None else None
    if archive is None or not archive.validity_months or not sub.upload_date:
        return None
    return to_local_timezone(_add_months(sub.upload_date, archive.validity_months))


def overrides(up: UserProgram) -> dict:
    """{(archive_id, kind): ConclusionRequirementOverride} of the student program."""
    rows = ConclusionRequirementOverride.query.filter_by(user_program_id=up.id).all()
    return {(o.archive_id, o.kind): o for o in rows}


def _evaluate(up: UserProgram, ps: ProgramStep, archive: Archive, blocked_ids: set,
              decided: dict) -> dict:
    """One requirement item (see `requirements`)."""
    sub = _latest_submission(up, archive.id)
    reused_from = None
    expires_at = None
    note = None
    not_applicable = decided.get((archive.id, 'not_applicable'))
    if not_applicable is not None:
        # The coordination's decision wins over whatever was delivered.
        status = 'not_applicable'
        note = not_applicable.reason
    elif archive.issued_by_institution:
        status = 'institution_done' if sub is not None and sub.status == 'approved' \
            else 'institution_pending'
    elif sub is not None:
        # The student's own submission wins over reuse, whatever its status.
        status = sub.status if sub.status in ('approved', 'pending', 'rejected') \
            else 'pending'
    else:
        reused_from = _reuse_source(up, archive, blocked_ids)
        if reused_from is None:
            status = 'missing'
        else:
            expires_at = reuse_expires_at(reused_from)
            status = 'reused'
            if expires_at is not None and expires_at < now_local():
                if (archive.id, 'accept_expired') in decided:
                    note = EXPIRED_ACCEPTED_NOTE
                else:
                    status = 'reused_expired'
    return {
        'archive': archive,
        'program_step': ps,
        'status': status,
        'submission': sub,
        'reused_from': reused_from,
        'reuse_expires_at': expires_at,
        'note': note,
        'overrides': {kind: o for (aid, kind), o in decided.items() if aid == archive.id},
        'satisfied': status in SATISFIED_STATUSES,
        'blocked_by_condition': archive.id in blocked_ids,
    }


def requirements(up: UserProgram) -> list:
    """
    Conclusion requirements of the student's program with their state.

    Each item: {
        'archive': Archive, 'program_step': ProgramStep,
        'status': 'approved' | 'pending' | 'rejected' | 'missing' | 'reused'
                  | 'reused_expired' | 'not_applicable'
                  | 'institution_pending' | 'institution_done',
        'submission': Submission | None,   # the student's (or coordination's) own
        'reused_from': Submission | None,  # admission submission when reused
        'reuse_expires_at': datetime | None,
        'note': str | None,                # override reason / accepted-expiry note
        'overrides': {kind: ConclusionRequirementOverride},
        'satisfied': bool,
        'blocked_by_condition': bool,      # a pending condition points at it
    }
    """
    blocked_ids = {c.archive_id for c in conditions(up)
                   if c.status == 'pending' and c.archive_id is not None}
    decided = overrides(up)
    return [_evaluate(up, ps, archive, blocked_ids, decided)
            for ps, archive in conclusion_archives(up.program_id)]


def requirement_satisfied(up: UserProgram, archive_id: int) -> bool:
    """Whether the requirement `archive_id` is satisfied now, ignoring conditions."""
    for ps, archive in conclusion_archives(up.program_id):
        if archive.id == archive_id:
            return _evaluate(up, ps, archive, set(), overrides(up))['satisfied']
    return False


def set_requirement_override(actor, user_program_id: int, archive_uuid, kind: str,
                             reason: str) -> ConclusionRequirementOverride:
    """
    Record a coordination decision on one requirement of one student:
    'not_applicable' (counts as satisfied) or 'accept_expired' (a reused
    admission document past its validity counts as reused). Reason
    mandatory. Commits.
    """
    if kind not in OVERRIDE_KINDS:
        raise ConclusionError('Decisión inválida.')
    up = _locked(actor, user_program_id)
    _require_writable(up, 'modificar requisitos')
    ps, archive = _program_archive(up, archive_uuid)
    reason = _clean(reason)
    if not reason:
        raise ConclusionError('El motivo es obligatorio.')
    decided = overrides(up)
    if (archive.id, kind) in decided:
        raise ConclusionConflict('Ese requisito ya tiene esa decisión registrada.')
    item = _evaluate(up, ps, archive, set(), decided)
    if kind == 'accept_expired' and item['status'] != 'reused_expired':
        raise ConclusionError(
            'Sólo se acepta la vigencia vencida de un documento reutilizado de admisión.')
    if kind == 'not_applicable' and item['status'] in ('approved', 'institution_done', 'reused'):
        raise ConclusionError(
            'El requisito ya está cumplido; no hace falta marcarlo como «no aplica».')

    override = ConclusionRequirementOverride(user_program_id=up.id, archive_id=archive.id,
                                             kind=kind, reason=reason, created_by=actor.id)
    db.session.add(override)
    db.session.flush()
    UserHistoryService.log_action(
        user_id=up.user_id, action='conclusion_requirement_override_set', admin_id=actor.id,
        user_program_id=up.id,
        details={'program_id': up.program_id, 'archive_name': archive.name, 'kind': kind,
                 'reason': reason},
    )
    _notify_student(up, 'conclusion_requirement_override',
                    'Cambio en tus requisitos de conclusión',
                    f'"{archive.name}": {OVERRIDE_LABELS_ES[kind]}. Motivo: {reason}')
    db.session.commit()
    return override


def remove_requirement_override(actor, user_program_id: int, archive_uuid, kind: str) -> None:
    """Undo a 'not_applicable' / 'accept_expired' decision. Commits."""
    up = _locked(actor, user_program_id)
    _require_writable(up, 'modificar requisitos')
    _, archive = _program_archive(up, archive_uuid)
    override = overrides(up).get((archive.id, kind))
    if override is None:
        raise ConclusionNotFound('Decisión no encontrada.')
    reason = override.reason
    db.session.delete(override)
    UserHistoryService.log_action(
        user_id=up.user_id, action='conclusion_requirement_override_removed', admin_id=actor.id,
        user_program_id=up.id,
        details={'program_id': up.program_id, 'archive_name': archive.name, 'kind': kind,
                 'previous_reason': reason},
    )
    _notify_student(up, 'conclusion_requirement_override',
                    'Cambio en tus requisitos de conclusión',
                    f'"{archive.name}": la coordinación retiró «{OVERRIDE_LABELS_ES[kind]}».')
    db.session.commit()


# ─── Thesis ──────────────────────────────────────────────────────────────────

def _require_thesis_status(up: UserProgram) -> None:
    if effective_status(up) not in THESIS_STATUSES:
        label = status_svc.STATUS_LABELS_ES.get(up.academic_status, up.academic_status)
        raise ConclusionError(
            f'No se puede modificar la tesis con estado académico "{label}".')


def _clean(value: Optional[str]) -> Optional[str]:
    value = (value or '').strip()
    return value or None


#: Where the student follows their conclusion.
STUDENT_CONCLUSION_URL = '/conclusion/'


def _notify_student(up: UserProgram, notification_type: str, title: str, message: str,
                    priority: str = 'low') -> None:
    """Short notice to the student about a change in their conclusion file."""
    NotificationService.create_notification(
        user_id=up.user_id, notification_type=notification_type, title=title,
        message=message, priority=priority, action_url=STUDENT_CONCLUSION_URL,
        data={'program_id': up.program_id},
    )


def register_thesis(actor, user_program_id: int, title: str, research_line: Optional[str] = None,
                    registered_at: Optional[date] = None) -> Thesis:
    """Register the thesis of a student program (once). Commits."""
    up = _locked(actor, user_program_id)
    _require_thesis_status(up)
    title = _clean(title)
    if not title:
        raise ConclusionError('El título de la tesis es obligatorio.')
    if get_thesis(up) is not None:
        raise ConclusionConflict('La tesis ya está registrada.')
    registered_at = registered_at or now_local().date()
    if registered_at > now_local().date():
        raise ConclusionError('La fecha de registro no puede ser futura.')

    thesis = Thesis(user_program_id=up.id, title=title, research_line=_clean(research_line),
                    registered_at=registered_at, created_by=actor.id)
    db.session.add(thesis)
    db.session.flush()
    UserHistoryService.log_action(
        user_id=up.user_id, action='thesis_registered', admin_id=actor.id,
        user_program_id=up.id,
        details={'program_id': up.program_id, 'title': title,
                 'registered_at': registered_at.isoformat()},
    )
    _notify_student(up, 'thesis_registered', 'Tesis registrada',
                    f'La coordinación registró tu tesis "{title}".')
    db.session.commit()
    return thesis


def update_thesis(actor, user_program_id: int, *, title: Optional[str] = None,
                  research_line: Optional[str] = None,
                  registered_at: Optional[date] = None) -> Thesis:
    """Edit title / research line / registration date. Logs old → new. Commits."""
    up = _locked(actor, user_program_id)
    _require_thesis_status(up)
    thesis = get_thesis(up)
    if thesis is None:
        raise ConclusionNotFound('La tesis no está registrada.')

    changes = {}
    if title is not None:
        title = _clean(title)
        if not title:
            raise ConclusionError('El título de la tesis es obligatorio.')
        if title != thesis.title:
            changes['title'] = {'from': thesis.title, 'to': title}
            thesis.title = title
    if research_line is not None:
        research_line = _clean(research_line)
        if research_line != thesis.research_line:
            changes['research_line'] = {'from': thesis.research_line, 'to': research_line}
            thesis.research_line = research_line
    if registered_at is not None and registered_at != thesis.registered_at:
        if registered_at > now_local().date():
            raise ConclusionError('La fecha de registro no puede ser futura.')
        changes['registered_at'] = {'from': thesis.registered_at.isoformat(),
                                    'to': registered_at.isoformat()}
        thesis.registered_at = registered_at

    if changes:
        UserHistoryService.log_action(
            user_id=up.user_id, action='thesis_updated', admin_id=actor.id,
            user_program_id=up.id,
            details={'program_id': up.program_id, 'changes': changes},
        )
    db.session.commit()
    return thesis


def add_member(actor, user_program_id: int, body: str, role: str, *,
               user_id: Optional[int] = None, external_name: Optional[str] = None,
               external_institution: Optional[str] = None) -> ThesisMember:
    """
    Add a person to the tutorial committee or the examination board.

    Internal (`user_id`, an active user) or external (`external_name`,
    optional institution) — exactly one. One director per thesis; one
    president and one secretary per board. Commits.
    """
    up = _locked(actor, user_program_id)
    _require_thesis_status(up)
    thesis = get_thesis(up)
    if thesis is None:
        raise ConclusionError('Primero registra la tesis.')
    if body not in MEMBER_ROLES:
        raise ConclusionError('Cuerpo inválido: debe ser comité tutorial o sínodo.')
    if role not in MEMBER_ROLES[body]:
        raise ConclusionError(
            f'El rol "{ROLE_LABELS_ES.get(role, role)}" no corresponde al {BODY_LABELS_ES[body]}.')
    if body == 'exam' and current_exam(up) is not None:
        raise ConclusionConflict('No se puede modificar el sínodo con un examen agendado.')

    external_name = _clean(external_name)
    external_institution = _clean(external_institution)
    if user_id is not None and external_name:
        raise ConclusionError('Indica un usuario interno o un externo, no ambos.')
    if user_id is None and not external_name:
        raise ConclusionError('El nombre del integrante externo es obligatorio.')

    person = None
    if user_id is not None:
        from app.services import teacher_service

        person = db.session.get(User, user_id)
        if person is None or not person.is_active:
            raise ConclusionError('El usuario no existe o está inactivo.')
        if person.id not in {u.id for u in teacher_service.teacher_choices()}:
            raise ConclusionError(
                'Sólo personal interno de la institución puede integrarse como usuario; '
                'registra a los demás como integrantes externos.')
        if person.id == up.user_id:
            raise ConclusionError('El estudiante no puede integrar su propio comité.')
        if any(m.user_id == person.id for m in thesis.members_of(body)):
            raise ConclusionConflict(f'Esa persona ya integra el {BODY_LABELS_ES[body]}.')
        external_institution = None

    unique_roles = {'tutorial': ('director',), 'exam': ('president', 'secretary')}[body]
    if role in unique_roles and any(m.role == role for m in thesis.members_of(body)):
        raise ConclusionConflict(
            f'El {BODY_LABELS_ES[body]} ya tiene {ROLE_LABELS_ES[role]}.')

    member = ThesisMember(thesis_id=thesis.id, body=body, role=role,
                          user_id=person.id if person else None,
                          external_name=None if person else external_name,
                          external_institution=external_institution)
    db.session.add(member)
    db.session.flush()
    db.session.refresh(thesis)
    UserHistoryService.log_action(
        user_id=up.user_id, action='thesis_member_added', admin_id=actor.id,
        user_program_id=up.id,
        details={'program_id': up.program_id, 'body': body, 'role': role,
                 'name': member.display_name, 'external': person is None,
                 'institution': external_institution},
    )
    _notify_student(up, 'thesis_member_added', f'Cambio en tu {BODY_LABELS_ES[body]}',
                    f'{member.display_name} se integró a tu {BODY_LABELS_ES[body]} como '
                    f'{ROLE_LABELS_ES[role]}.')
    db.session.commit()
    return member


def remove_member(actor, user_program_id: int, member_id: int) -> None:
    """Remove a committee/board member of this student's thesis. Commits."""
    up = _locked(actor, user_program_id)
    _require_thesis_status(up)
    thesis = get_thesis(up)
    member = db.session.get(ThesisMember, member_id) if member_id else None
    if thesis is None or member is None or member.thesis_id != thesis.id:
        raise ConclusionNotFound(MEMBER_NOT_FOUND_MESSAGE)
    if member.body == 'exam' and current_exam(up) is not None:
        raise ConclusionConflict('No se puede modificar el sínodo con un examen agendado.')

    details = {'program_id': up.program_id, 'body': member.body, 'role': member.role,
               'name': member.display_name, 'external': member.is_external}
    db.session.delete(member)
    UserHistoryService.log_action(
        user_id=up.user_id, action='thesis_member_removed', admin_id=actor.id,
        user_program_id=up.id, details=details,
    )
    body_label = BODY_LABELS_ES[details['body']]
    _notify_student(up, 'thesis_member_removed', f'Cambio en tu {body_label}',
                    f'{details["name"]} dejó de integrar tu {body_label}.')
    db.session.commit()


# ─── Admission conditions ────────────────────────────────────────────────────

#: Resolution note of a condition born against an already satisfied requirement.
ALREADY_MET_NOTE = 'Requisito ya cumplido al registrar la condición'


def stage_condition(up: UserProgram, description: str, *, archive_id: Optional[int] = None,
                    due_date: Optional[date] = None, actor_id: Optional[int] = None
                    ) -> AdmissionCondition:
    """Add a pending condition + its history entry. No scope check, no commit."""
    description = _clean(description)
    if not description:
        raise ConclusionError('La descripción de la condición es obligatoria.')
    already_met = False
    if archive_id is not None:
        if archive_id not in {a.id for _, a in conclusion_archives(up.program_id)}:
            raise ConclusionError(
                'La condición sólo puede ligarse a un requisito de conclusión del programa.')
        # Evaluated before the condition exists: a pending condition would
        # itself block the reuse it is asking about.
        already_met = requirement_satisfied(up, archive_id)
    condition = AdmissionCondition(user_program_id=up.id, description=description,
                                   archive_id=archive_id, due_date=due_date,
                                   status='pending', created_by=actor_id)
    db.session.add(condition)
    db.session.flush()
    UserHistoryService.log_action(
        user_id=up.user_id, action='admission_condition_created', admin_id=actor_id,
        user_program_id=up.id,
        details={'program_id': up.program_id, 'description': description,
                 'archive_id': archive_id,
                 'due_date': due_date.isoformat() if due_date else None},
    )
    if already_met:
        _mark_resolved(up, condition, 'met', ALREADY_MET_NOTE, actor_id)
    return condition


def create_condition(actor, user_program_id: int, description: str, *,
                     archive_uuid=None, due_date: Optional[date] = None) -> AdmissionCondition:
    """Add a condition to an accepted student program (not titled/withdrawn). Commits."""
    up = _locked(actor, user_program_id)
    _require_writable(up, 'agregar condiciones')
    archive_id = None
    if archive_uuid:
        _, archive = _program_archive(up, archive_uuid)
        archive_id = archive.id
    condition = stage_condition(up, description, archive_id=archive_id, due_date=due_date,
                                actor_id=actor.id)
    _notify_student(up, 'admission_condition_created', 'Nueva condición de aceptación',
                    f'La coordinación registró una condición: {condition.description}',
                    priority='medium')
    db.session.commit()
    return condition


def _mark_resolved(up: UserProgram, condition: AdmissionCondition, resolution: str,
                   note: Optional[str], actor_id: Optional[int]) -> None:
    """Write the resolution + history + student notice. No commit."""
    condition.status = resolution
    condition.resolved_at = now_local()
    condition.resolved_by = actor_id
    condition.resolution_note = note
    UserHistoryService.log_action(
        user_id=up.user_id, action='admission_condition_resolved', admin_id=actor_id,
        user_program_id=up.id,
        details={'program_id': up.program_id, 'description': condition.description,
                 'resolution': resolution, 'note': note},
    )
    verb = 'dispensada' if resolution == 'waived' else 'cumplida'
    _notify_student(up, 'admission_condition_resolved', f'Condición {verb}',
                    f'Tu condición de aceptación quedó {verb}: {condition.description}')


def resolve_condition(actor, user_program_id: int, condition_uuid, resolution: str,
                      note: Optional[str] = None) -> AdmissionCondition:
    """
    Mark a pending condition of `user_program_id` as met or waived (waiving
    needs a note). A condition of another student program is a 404. Commits.
    """
    condition = AdmissionCondition.by_uuid(condition_uuid)
    up = db.session.get(UserProgram, user_program_id) if user_program_id else None
    if condition is None or up is None or condition.user_program_id != up.id \
            or not _in_scope(actor, up):
        raise ConclusionNotFound(CONDITION_NOT_FOUND_MESSAGE)
    up = _locked(actor, up.id)
    condition = (AdmissionCondition.query.filter_by(id=condition.id)
                 .with_for_update().populate_existing().first())
    if condition is None:
        raise ConclusionNotFound(CONDITION_NOT_FOUND_MESSAGE)
    _require_writable(up, 'resolver condiciones')
    if resolution not in ('met', 'waived'):
        raise ConclusionError('Resolución inválida: debe ser cumplida o dispensada.')
    if condition.status != 'pending':
        raise ConclusionConflict('La condición ya fue resuelta.')
    note = _clean(note)
    if resolution == 'waived' and not note:
        raise ConclusionError('El motivo de la dispensa es obligatorio.')

    _mark_resolved(up, condition, resolution, note, actor.id)
    db.session.commit()
    return condition


AUTO_RESOLVE_NOTE = 'Cumplida al aprobarse el requisito'


def on_requirement_approved(submission: Submission, reviewer_id: Optional[int]) -> list:
    """
    The review inbox approved `submission`: every pending condition of the
    same student program that points at its archive becomes met. Called
    inside the reviewer's transaction; no commit. Returns the conditions.
    """
    if submission is None or submission.user_program_id is None \
            or submission.archive_id is None:
        return []
    pending = (AdmissionCondition.query
               .filter_by(user_program_id=submission.user_program_id,
                          archive_id=submission.archive_id, status='pending')
               .with_for_update().populate_existing().all())
    if not pending:
        return []
    up = db.session.get(UserProgram, submission.user_program_id)
    for condition in pending:
        _mark_resolved(up, condition, 'met', AUTO_RESOLVE_NOTE, reviewer_id)
    return pending


# ─── Requirement uploads ─────────────────────────────────────────────────────

def upload_requirement(user, archive_uuid, user_program_id: int, file) -> Submission:
    """
    The student uploads (or replaces) a conclusion requirement.

    Only the owner of the student program, only once graduated, never for a
    document the institution issues, never over an approved one. The
    submission goes to the review inbox as 'pending'. Commits.
    """
    from app.utils.files import save_user_doc

    up = None
    if user_program_id:
        # Lock the student program: two concurrent uploads must not both
        # create a submission for the same requirement.
        up = (UserProgram.query.filter_by(id=user_program_id)
              .with_for_update().populate_existing().first())
    if up is None or up.user_id != user.id:
        raise ConclusionNotFound(STUDENT_NOT_FOUND_MESSAGE)
    if file is None:
        raise ConclusionError('Selecciona un archivo.')
    ps, archive = _program_archive(up, archive_uuid)
    if effective_status(up) != status_svc.GRADUATED:
        raise ConclusionError('Los requisitos de conclusión se entregan después del egreso.')
    if archive.issued_by_institution:
        raise ConclusionError('Este documento lo emite la institución; la coordinación lo carga.')

    if (archive.id, 'not_applicable') in overrides(up):
        raise ConclusionError('La coordinación marcó este requisito como «no aplica».')

    sub = _latest_submission(up, archive.id)
    if sub is not None and sub.status == 'approved':
        raise ConclusionConflict('Este documento ya fue aprobado.')

    rel = save_user_doc(file, user.id, phase=CONCLUSION_PHASE, name=_file_name(archive, up))
    if sub is None:
        sub = Submission(file_path=rel, status='pending', user_id=user.id,
                         archive_id=archive.id, program_step_id=ps.id, semester=None,
                         uploaded_by=user.id, uploaded_by_role='student',
                         user_program_id=up.id)
        db.session.add(sub)
    sub.program_step_id = ps.id
    sub.user_program_id = up.id
    sub.file_path = rel
    sub.status = 'pending'
    sub.upload_date = now_local()
    sub.uploaded_by = user.id
    sub.uploaded_by_role = 'student'
    sub.reviewer_id = None
    sub.review_date = None
    db.session.flush()

    UserHistoryService.log_document_upload(
        user_id=user.id, archive_name=archive.name,
        program_name=up.program.name if up.program else '',
        uploaded_by_admin=False,
    )
    coordinator_id = up.program.coordinator_id if up.program else None
    if coordinator_id:
        NotificationService.create_notification(
            user_id=coordinator_id,
            notification_type='document_submitted',
            title='Nuevo documento de conclusión',
            message=(f'{user.first_name} {user.last_name} subió "{archive.name}" '
                     f'en {up.program.name}.'),
            priority='low',
            action_url='/admin/review',
            data={'program_id': up.program_id},
        )
    db.session.commit()
    return sub


def _file_name(archive: Archive, up: UserProgram) -> str:
    """Stored file name of a conclusion document: unique per archive and student program."""
    return f'{archive.archive_key or archive.id}_up{up.id}'


#: Statuses in which the coordination may upload an institution document.
INSTITUTION_UPLOAD_STATUSES = frozenset({status_svc.GRADUATED, status_svc.TITLED})


def upload_institution_document(actor, up: UserProgram, archive, file) -> Submission:
    """
    The coordination uploads a document the institution issues
    (`Archive.issued_by_institution`), once the student is graduated or
    titled; it is born approved (uploaded_by_role='coordinator'). Commits.
    """
    from app.utils.files import save_user_doc

    up = _locked(actor, up.id if isinstance(up, UserProgram) else up)
    if file is None:
        raise ConclusionError('Selecciona un archivo.')
    ps, archive = _program_archive(up, archive)
    if not archive.issued_by_institution:
        raise ConclusionError('Este documento lo entrega el estudiante.')
    if effective_status(up) not in INSTITUTION_UPLOAD_STATUSES:
        raise ConclusionError(
            'Los documentos de conclusión se cargan cuando el estudiante está egresado o titulado.')

    sub = _latest_submission(up, archive.id)
    replaced = sub.file_path if sub is not None else None
    rel = save_user_doc(file, up.user_id, phase=CONCLUSION_PHASE, name=_file_name(archive, up))
    now = now_local()
    if sub is None:
        sub = Submission(file_path=rel, status='approved', user_id=up.user_id,
                         archive_id=archive.id, program_step_id=ps.id, semester=None,
                         uploaded_by=actor.id, uploaded_by_role='coordinator',
                         user_program_id=up.id)
        db.session.add(sub)
    sub.program_step_id = ps.id
    sub.user_program_id = up.id
    sub.file_path = rel
    sub.status = 'approved'
    sub.upload_date = now
    sub.uploaded_by = actor.id
    sub.uploaded_by_role = 'coordinator'
    sub.reviewer_id = actor.id
    sub.review_date = now
    db.session.flush()

    UserHistoryService.log_action(
        user_id=up.user_id, action='institution_document_uploaded', admin_id=actor.id,
        user_program_id=up.id,
        details={'program_id': up.program_id, 'archive_name': archive.name,
                 'file_path': rel, 'replaced_file_path': replaced},
    )
    NotificationService.create_notification(
        user_id=up.user_id,
        notification_type='document_approved',
        title='Documento de conclusión disponible',
        message=f'La coordinación cargó "{archive.name}" en tu expediente de conclusión.',
        priority='medium',
        action_url='/user/dashboard',
    )
    db.session.commit()
    return sub


# ─── Grade exam ──────────────────────────────────────────────────────────────

def exam_blockers(up: UserProgram) -> list:
    """Why the exam cannot be scheduled yet (Spanish), empty when it can."""
    return _blockers(up, requirements(up))


def _blockers(up: UserProgram, items: list) -> list:
    """`exam_blockers` over already computed `requirements(up)` items."""
    status = effective_status(up)
    if status == status_svc.TITLED:
        return ['El estudiante ya está titulado.']
    blockers = []
    if status != status_svc.GRADUATED:
        blockers.append('El estudiante debe estar egresado.')
    thesis = get_thesis(up)
    if thesis is None:
        blockers.append('Falta registrar la tesis.')
    for item in items:
        if not item['satisfied']:
            blockers.append(f'Requisito sin aprobar: {item["archive"].name}.')
    for condition in conditions(up):
        if condition.status == 'pending':
            blockers.append(f'Condición de aceptación pendiente: {condition.description}')
    if thesis is not None:
        roles = {m.role for m in thesis.members_of('exam')}
        missing = [ROLE_LABELS_ES[r] for r in REQUIRED_EXAM_ROLES if r not in roles]
        if missing:
            blockers.append(f'Falta integrar el sínodo: {", ".join(missing)}.')
    else:
        blockers.append('Falta integrar el sínodo: presidente(a), secretario(a), vocal.')
    return blockers


def _get_exam(actor, user_program_id: int, exam_uuid) -> tuple:
    """(exam, locked up): the exam must belong to `user_program_id` (else 404)."""
    exam = GradeExam.by_uuid(exam_uuid)
    up = db.session.get(UserProgram, user_program_id) if user_program_id else None
    if exam is None or up is None or exam.user_program_id != up.id or not _in_scope(actor, up):
        raise ConclusionNotFound(EXAM_NOT_FOUND_MESSAGE)
    up = _locked(actor, up.id)
    db.session.refresh(exam)
    return exam, up


def _naive_now() -> datetime:
    """Local wall-clock now without tzinfo (exam datetimes are stored naive)."""
    return now_local().replace(tzinfo=None)


def _fmt_when(value: datetime) -> str:
    from app.utils.datetime_utils import format_date_es, format_time_es
    return f'{format_date_es(value)} a las {format_time_es(value)}'


def schedule_exam(actor, user_program_id: int, scheduled_at: datetime, place: str,
                  notes: Optional[str] = None) -> GradeExam:
    """Schedule the grade exam (no blockers, one at a time). Commits."""
    up = _locked(actor, user_program_id)
    place = _clean(place)
    if scheduled_at is None:
        raise ConclusionError('La fecha y hora del examen son obligatorias.')
    if not place:
        raise ConclusionError('El lugar del examen es obligatorio.')
    naive = scheduled_at.replace(tzinfo=None) if scheduled_at.tzinfo else scheduled_at
    if naive < _naive_now():
        raise ConclusionError('La fecha y hora del examen no pueden estar en el pasado.')
    if current_exam(up) is not None:
        raise ConclusionConflict('Ya hay un examen de grado agendado.')
    blockers = exam_blockers(up)
    if blockers:
        raise ConclusionError('No se puede agendar el examen: ' + ' '.join(blockers),
                              fields={'blockers': blockers})

    exam = GradeExam(user_program_id=up.id, scheduled_at=scheduled_at, place=place,
                     status='scheduled', notes=_clean(notes), scheduled_by=actor.id,
                     honorific_mention=False)
    db.session.add(exam)
    db.session.flush()
    when = _fmt_when(scheduled_at)
    UserHistoryService.log_action(
        user_id=up.user_id, action='grade_exam_scheduled', admin_id=actor.id,
        user_program_id=up.id,
        details={'program_id': up.program_id, 'scheduled_at': scheduled_at.isoformat(),
                 'place': place},
    )
    NotificationService.create_notification(
        user_id=up.user_id,
        notification_type='grade_exam_scheduled',
        title='Examen de grado agendado',
        message=f'Tu examen de grado quedó agendado para el {when} en {place}.',
        priority='high',
        action_url='/user/dashboard',
    )
    db.session.commit()
    return exam


def record_exam_result(actor, user_program_id: int, exam_uuid, result: str, *,
                       verdict: Optional[str] = None,
                       honorific_mention: bool = False, acta_folio: Optional[str] = None,
                       held_on: Optional[date] = None, notes: Optional[str] = None) -> GradeExam:
    """
    Record the outcome of a scheduled exam.

    'approved' needs verdict (unanimous|majority), acta folio and date, and
    the exam blockers re-checked (a requirement may have been rejected or a
    condition added since scheduling); it titles the student with `held_on`
    as `titled_at`. 'suspended' keeps the student graduated so a new exam
    can be scheduled. `held_on` is neither future nor before the scheduled
    date. Commits.
    """
    exam, up = _get_exam(actor, user_program_id, exam_uuid)
    if exam.status != 'scheduled':
        raise ConclusionConflict('El examen ya tiene resultado o fue cancelado.')
    if result not in ('approved', 'suspended'):
        raise ConclusionError('Resultado inválido: debe ser aprobado o suspendido.')
    held_on = held_on or exam.scheduled_at.date()
    if held_on > now_local().date():
        raise ConclusionError('La fecha del examen no puede ser futura.')
    if held_on < exam.scheduled_at.date():
        raise ConclusionError('La fecha del examen no puede ser anterior a la fecha agendada.')
    acta_folio = _clean(acta_folio)

    if result == 'approved':
        if verdict not in EXAM_VERDICTS:
            raise ConclusionError('Indica si fue aprobado por unanimidad o por mayoría.')
        if not acta_folio:
            raise ConclusionError('El folio del acta es obligatorio.')
        # exam_blockers never counts the scheduled exam itself as a blocker.
        blockers = exam_blockers(up)
        if blockers:
            raise ConclusionError('No se puede titular: ' + ' '.join(blockers),
                                  fields={'blockers': blockers})
        status_svc.transition(up, status_svc.TITLED, actor_id=actor.id, on_date=held_on)
    else:
        verdict = None
        honorific_mention = False

    exam.status = result
    exam.verdict = verdict
    exam.honorific_mention = bool(honorific_mention)
    exam.acta_folio = acta_folio
    exam.held_on = held_on
    exam.recorded_by = actor.id
    if notes is not None:
        exam.notes = _clean(notes)
    UserHistoryService.log_action(
        user_id=up.user_id, action='grade_exam_recorded', admin_id=actor.id,
        user_program_id=up.id,
        details={'program_id': up.program_id, 'result': result, 'verdict': verdict,
                 'honorific_mention': exam.honorific_mention, 'acta_folio': acta_folio,
                 'held_on': held_on.isoformat()},
    )
    if result == 'approved':
        title = 'Examen de grado aprobado'
        message = (f'Aprobaste tu examen de grado de {up.program.name}. ¡Felicidades!'
                   + (' Con mención honorífica.' if exam.honorific_mention else ''))
    else:
        title = 'Examen de grado suspendido'
        message = ('Tu examen de grado fue suspendido. La coordinación te informará '
                   'la nueva fecha.')
    NotificationService.create_notification(
        user_id=up.user_id, notification_type='grade_exam_result', title=title,
        message=message, priority='high', action_url='/user/dashboard',
    )
    db.session.commit()
    return exam


def cancel_exam(actor, user_program_id: int, exam_uuid,
                reason: Optional[str] = None) -> GradeExam:
    """Cancel a scheduled exam of `user_program_id` (before it is held). Commits."""
    exam, up = _get_exam(actor, user_program_id, exam_uuid)
    if exam.status != 'scheduled':
        raise ConclusionConflict('Sólo se cancela un examen agendado.')
    reason = _clean(reason)
    exam.status = 'cancelled'
    exam.recorded_by = actor.id
    if reason:
        exam.notes = reason
    UserHistoryService.log_action(
        user_id=up.user_id, action='grade_exam_cancelled', admin_id=actor.id,
        user_program_id=up.id,
        details={'program_id': up.program_id, 'scheduled_at': exam.scheduled_at.isoformat(),
                 'reason': reason},
    )
    NotificationService.create_notification(
        user_id=up.user_id, notification_type='grade_exam_cancelled',
        title='Examen de grado cancelado',
        message='Tu examen de grado agendado fue cancelado. La coordinación te informará.',
        priority='high', action_url='/user/dashboard',
    )
    db.session.commit()
    return exam


def revert_titled(actor, user_program_id: int, reason: str) -> UserProgram:
    """
    Undo a titling captured by mistake: `titled` → `graduated` (the route
    guarantees postgraduate_admin through `conclusion.page.revert_titled`).
    The approved exam stays as history. Commits.
    """
    up = _locked(actor, user_program_id)
    status_svc.transition(up, status_svc.GRADUATED, actor_id=actor.id, reason=reason,
                          allow_revert=True)
    NotificationService.create_notification(
        user_id=up.user_id, notification_type='enrollment_status_changed',
        title='Titulación revertida',
        message=f'Tu titulación en {up.program.name} fue revertida. Contacta a la coordinación.',
        priority='high', action_url='/user/dashboard',
    )
    db.session.commit()
    return up


# ─── Read models ─────────────────────────────────────────────────────────────

def progress(up: UserProgram) -> dict:
    """
    Conclusion progress for the coordinator dashboard:
    {'stage': code, 'label': Spanish, 'percent': 0-100}.
    """
    status = effective_status(up)

    def _out(stage, percent):
        return {'stage': stage, 'label': STAGE_LABELS_ES[stage], 'percent': int(percent)}

    if status == status_svc.TITLED:
        return _out('titled', 100)
    if status == status_svc.WITHDRAWN:
        return _out('closed', 0)
    if status == status_svc.GRADUATED:
        if current_exam(up) is not None:
            return _out('exam_scheduled', 90)
        items = requirements(up)
        if not _blockers(up, items):
            return _out('ready', 85)
        done = sum(1 for i in items if i['satisfied'])
        return _out('requirements', 40 + (40 * done // len(items) if items else 40))
    thesis = get_thesis(up)
    if thesis is None:
        return _out('not_started', 0)
    has_director = any(m.role == 'director' for m in thesis.members_of('tutorial'))
    return _out('thesis', 25 if has_director else 15)


def my_theses(user) -> list:
    """
    Theses where `user` sits on the tutorial committee (read-only page):
    [{'thesis', 'user_program', 'student', 'roles': [role...], 'progress'}].
    """
    members = (ThesisMember.query
               .filter_by(user_id=user.id, body='tutorial')
               .order_by(ThesisMember.thesis_id).all())
    by_thesis: dict = {}
    for m in members:
        by_thesis.setdefault(m.thesis_id, []).append(m.role)
    if not by_thesis:
        return []
    theses = (Thesis.query.filter(Thesis.id.in_(by_thesis))
              .order_by(Thesis.registered_at.desc(), Thesis.id.desc()).all())
    rows = []
    for thesis in theses:
        up = thesis.user_program
        rows.append({
            'thesis': thesis,
            'user_program': up,
            'student': up.user if up else None,
            'roles': by_thesis[thesis.id],
            'progress': progress(up) if up else None,
        })
    return rows

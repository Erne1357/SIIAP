# app/services/deliberation_service.py
"""
Servicio para gestionar el proceso de deliberacion de aspirantes.

El flujo de deliberacion es:
1. Aspirante completa entrevista -> admission_status = 'interview_completed'
2. Coordinador inicia deliberacion -> admission_status = 'deliberation'
3. Comite toma decision:
   - Aceptar -> admission_status = 'accepted'
   - Rechazar -> admission_status = 'rejected'
   - Solicitar correccion -> admission_status = 'rejected', rejection_type = 'partial'

ALCANCE: ninguna funcion de este modulo valida el alcance de programa del
llamador — recibe `program_id` y opera sobre el. Es responsabilidad de la ruta
declarar `@program_scope_required(program_id_kwarg='program_id')` (o
`guard_program_scope`) antes de llamar aqui. Todas las consultas estan
acotadas al `program_id` recibido, de modo que una ruta correctamente
protegida no puede tocar el expediente de otro programa.
"""

import json

from app import db
from app.services import public_id_service
from app.services.admission_status_service import (
    InvalidAdmissionTransition,
    lock_user_program,
    transition,
)
from app.models import UserProgram, User, Program, Submission, ProgramStep
from app.services.notification_service import NotificationService
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local
from sqlalchemy import and_, or_


from app.services.errors import DomainError, NotFoundError


class DeliberationError(DomainError):
    """Error base para operaciones de deliberacion."""
    pass


#: Denial text for "that applicant is not in this program". Carries no id: the
#: routes speak UUIDs now, so echoing the internal integer would hand it back
#: out, and a message that varies with the cause ("no such user" vs "user
#: exists but is not in this program") is an enumeration oracle.
APPLICANT_NOT_FOUND_MESSAGE = 'No se encontró al aspirante en este programa.'


class ApplicantNotFound(DeliberationError, NotFoundError):
    """El aspirante no fue encontrado."""
    pass


class InvalidStateTransition(DeliberationError):
    """Transicion de estado invalida."""
    pass


def get_applicants_for_deliberation(program_id: int):
    """
    Obtiene todos los aspirantes en estado de deliberacion para un programa.

    Args:
        program_id: ID del programa

    Returns:
        Lista de UserProgram con sus usuarios
    """
    return UserProgram.query.join(
        User, UserProgram.user_id == User.id
    ).filter(
        and_(
            UserProgram.program_id == program_id,
            UserProgram.admission_status.in_(['interview_completed', 'deliberation']),
            User.is_active == True,  # noqa: E712 — excluir cuentas desactivadas
        )
    ).order_by(UserProgram.deliberation_started_at.desc()).all()


def get_applicants_by_status(program_id: int, status: str):
    """
    Obtiene aspirantes de un programa por estado de admision.
    Excluye usuarios desactivados (User.is_active=False).

    Args:
        program_id: ID del programa
        status: Estado de admision a filtrar

    Returns:
        Lista de UserProgram
    """
    return UserProgram.query.join(
        User, UserProgram.user_id == User.id
    ).filter(
        and_(
            UserProgram.program_id == program_id,
            UserProgram.admission_status == status,
            User.is_active == True,  # noqa: E712
        )
    ).order_by(UserProgram.updated_at.desc()).all()


def get_user_program(user_id: int, program_id: int):
    """
    Obtiene el UserProgram de un usuario en un programa.

    Args:
        user_id: ID del usuario
        program_id: ID del programa

    Returns:
        UserProgram

    Raises:
        ApplicantNotFound: Si no existe la relacion
    """
    up = UserProgram.query.filter_by(
        user_id=user_id,
        program_id=program_id
    ).first()

    if not up:
        raise ApplicantNotFound(APPLICANT_NOT_FOUND_MESSAGE)

    return up


def get_user_program_for_update(user_id: int, program_id: int):
    """
    Same as `get_user_program` but takes a row lock (`SELECT ... FOR UPDATE`).

    Every function that changes `admission_status` loads the row this way so two
    concurrent decisions on the same applicant are serialised until commit.

    Raises:
        ApplicantNotFound: Si no existe la relacion
    """
    up = lock_user_program(user_id, program_id)

    if not up:
        raise ApplicantNotFound(APPLICANT_NOT_FOUND_MESSAGE)

    return up


def _move_to(up, to_status: str) -> None:
    """Run the state machine, surfacing a refusal as the module's own error."""
    try:
        transition(up, to_status)
    except InvalidAdmissionTransition as e:
        raise InvalidStateTransition(str(e)) from e


def _stage_interview_completed(up, user_id: int, program_id: int, actor_id: int,
                               details_suffix: str = ''):
    """Log history and queue the applicant notification for a completed interview."""
    program_name = up.program.name if up.program else f'programa {program_id}'
    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=actor_id,
        action='interview_completed',
        details=f'Entrevista marcada como completada en {program_name}{details_suffix}',
    )

    # 'medium' is this codebase's normal priority (low/medium/high/critical),
    # the same one start_deliberation uses for the next transition.
    NotificationService.create_notification(
        user_id=user_id,
        notification_type='interview_completed',
        title='Tu entrevista fue registrada',
        message=f'Tu entrevista para {program_name} quedó registrada como completada. '
                f'El siguiente paso es la deliberación del comité de admisión.',
        priority='medium',
        action_url='/user/dashboard',
    )


def _emit_interview_completed(user_id: int, program_id: int) -> None:
    """Notificar al aspirante + coordinadores del programa en tiempo real."""
    from app.sockets.emitters import emit_user_and_coordinators
    emit_user_and_coordinators(
        'admission:status_changed',
        {
            'user_id': public_id_service.user_uuid(user_id),
            'program_id': program_id,
            'new_status': 'interview_completed',
        },
        user_id=user_id,
        program_id=program_id,
    )


def mark_interview_completed(user_id: int, program_id: int, coordinator_id: int = None):
    """
    Marca que el aspirante completo su entrevista.
    Esto lo prepara para entrar en deliberacion.
    Tambien marca la cita (Appointment) como 'done' si existe.

    Args:
        user_id: ID del usuario
        program_id: ID del programa
        coordinator_id: ID del coordinador que marca la entrevista (para audit log)

    Returns:
        UserProgram actualizado
    """
    from app.models.appointment import Appointment
    from app.models.event import Event

    up = get_user_program_for_update(user_id, program_id)

    if up.admission_status not in ['in_progress']:
        raise InvalidStateTransition(
            f"No se puede marcar entrevista completada desde estado '{up.admission_status}'"
        )

    _move_to(up, 'interview_completed')

    # Buscar y marcar la cita de entrevista como 'done'.
    # Se incluyen eventos globales (program_id=NULL) además de los del programa,
    # pero un evento DEL PROGRAMA gana siempre: sin ese orden, un aspirante
    # inscrito en dos programas podía ver cerrada la cita del otro programa
    # sólo porque el `.first()` no era determinista.
    appointment = Appointment.query.join(
        Event, Appointment.event_id == Event.id
    ).filter(
        Appointment.applicant_id == user_id,
        or_(Event.program_id == program_id, Event.program_id.is_(None)),
        Event.type == 'interview',
        Appointment.status == 'scheduled'
    ).order_by(
        (Event.program_id == program_id).desc(),
        Appointment.id,
    ).first()

    if appointment:
        appointment.status = 'done'

    _stage_interview_completed(
        up, user_id, program_id, coordinator_id or user_id,
        details_suffix=f' (cita #{appointment.id})' if appointment else '',
    )

    db.session.commit()

    _emit_interview_completed(user_id, program_id)

    return up


def complete_interview_from_appointment(appointment, actor_id: int) -> bool:
    """
    Advance the applicant to `interview_completed` after an interview
    appointment was marked as done.

    Only acts when the appointment belongs to an `interview` event of a program
    and the applicant is still `in_progress` in it; anything else is a silent
    no-op (a non-interview appointment, a global event, an applicant who is
    already further along or not enrolled).

    Commits the session in every case — including whatever the caller already
    changed on the appointment — so the caller must not commit again. Returns
    True when the status moved.
    """
    from app.models.event import Event

    event = db.session.get(Event, appointment.event_id)
    if not event or event.type != 'interview' or not event.program_id:
        db.session.commit()
        return False

    up = lock_user_program(appointment.applicant_id, event.program_id)
    if not up or up.admission_status != 'in_progress':
        db.session.commit()
        return False

    _move_to(up, 'interview_completed')
    _stage_interview_completed(
        up, appointment.applicant_id, event.program_id, actor_id,
        details_suffix=f' (cita #{appointment.id}: {event.title})',
    )
    db.session.commit()

    _emit_interview_completed(appointment.applicant_id, event.program_id)
    return True


def start_deliberation(user_id: int, program_id: int, coordinator_id: int):
    """
    Inicia el proceso de deliberacion para un aspirante.

    Args:
        user_id: ID del usuario aspirante
        program_id: ID del programa
        coordinator_id: ID del coordinador que inicia la deliberacion

    Returns:
        UserProgram actualizado
    """
    up = get_user_program_for_update(user_id, program_id)

    if up.admission_status not in ['interview_completed']:
        raise InvalidStateTransition(
            f"Solo se puede iniciar deliberacion desde 'interview_completed', estado actual: '{up.admission_status}'"
        )

    up.start_deliberation()

    # Registrar en historial (en la misma transaccion)
    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=coordinator_id,
        action='deliberation_started',
        details='Proceso de deliberacion iniciado'
    )

    # Notificar al aspirante que su proceso está en deliberación
    program = Program.query.get(program_id)
    program_name = program.name if program else 'tu programa'
    NotificationService.create_notification(
        user_id=user_id,
        notification_type='deliberation_started',
        title='Tu expediente está en deliberación',
        message=f'El comité de admisión de {program_name} ha iniciado la revisión de tu expediente. '
                f'Te notificaremos cuando haya una resolución.',
        priority='medium',
        action_url='/user/dashboard',
    )

    db.session.commit()

    # Notificar al aspirante + coordinadores del programa en tiempo real
    from app.sockets.emitters import emit_user_and_coordinators
    emit_user_and_coordinators(
        'admission:status_changed',
        {
            'user_id': public_id_service.user_uuid(user_id),
            'program_id': program_id,
            'new_status': 'deliberation',
        },
        user_id=user_id,
        program_id=program_id,
    )

    return up


def accept_applicant(user_id: int, program_id: int, decision_by: int, notes: str = None,
                     is_conditional: bool = False, dictamen_file=None, conditions=None):
    """
    Acepta a un aspirante en el programa.

    Args:
        user_id: ID del aspirante
        program_id: ID del programa
        decision_by: ID del usuario que toma la decision
        notes: Notas opcionales sobre la decision
        is_conditional: Si True, marca la aceptación como condicionada (requiere dictamen)
        dictamen_file: FileStorage con el "Dictamen de Aceptación" (obligatorio si is_conditional)
        conditions: (Fase 6C) condiciones de la aceptación condicionada, cada una
            {description, archive_key|None, due_date|None} (dict u objeto con esos
            atributos). Se ignoran si la aceptación no es condicionada.

    Returns:
        UserProgram actualizado
    """
    from app.models.acceptance_document import AcceptanceDocument
    from app.utils.files import save_user_doc

    up = get_user_program_for_update(user_id, program_id)

    if up.admission_status not in ['deliberation', 'interview_completed']:
        raise InvalidStateTransition(
            f"Solo se puede aceptar desde 'deliberation' o 'interview_completed', estado actual: '{up.admission_status}'"
        )

    if is_conditional and not dictamen_file:
        raise ValueError(
            "Para aceptación condicionada se requiere adjuntar el 'Dictamen de Aceptación' (archivo PDF)."
        )

    # Resolve the condition keys before writing anything: an unknown key aborts.
    staged_conditions = _resolve_conditions(conditions, program_id) if is_conditional else []

    up.accept(decision_by=decision_by, notes=notes)

    if staged_conditions:
        from app.services import conclusion_service
        for description, archive_id, due_date in staged_conditions:
            conclusion_service.stage_condition(
                up, description, archive_id=archive_id, due_date=due_date,
                actor_id=decision_by,
            )

    # Obtener datos para notificacion
    user = User.query.get(user_id)
    program = Program.query.get(program_id)

    # Guardar Dictamen de Aceptación cuando es aceptación condicionada
    if is_conditional and dictamen_file:
        file_path = save_user_doc(dictamen_file, user_id, 'acceptance', 'dictamen_aceptacion')
        dictamen = AcceptanceDocument.query.filter_by(
            user_program_id=up.id,
            document_type='acceptance_opinion',
        ).first()
        if not dictamen:
            dictamen = AcceptanceDocument(
                user_program_id=up.id,
                document_type='acceptance_opinion',
            )
            db.session.add(dictamen)
        dictamen.file_path = file_path
        dictamen.uploaded_by_id = decision_by
        dictamen.uploaded_at = now_local()
        dictamen.status = 'uploaded'
        dictamen.review_notes = notes

    # Registrar en historial (en la misma transaccion)
    history_action = 'admission_accepted_conditional' if is_conditional else 'admission_accepted'
    history_details = (
        f'Aceptación condicionada en {program.name}. {notes or ""}'
        if is_conditional else
        f'Aceptado en {program.name}. {notes or ""}'
    )
    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=decision_by,
        action=history_action,
        details=history_details,
    )

    # Notificar al aspirante con email (en la misma transaccion)
    # Pinned to APP_BASE_URL: this URL is embedded in an e-mail body, so it must
    # not be rebuilt from the live request host (the requester controls `Host`).
    from app.utils.urls import external_url, get_base_url
    try:
        dashboard_url = external_url('pages_user.dashboard')
    except Exception:
        # Only reachable without an application context, which neither a route
        # nor a Celery ContextTask can be. Stay absolute anyway.
        dashboard_url = f"{get_base_url()}/user/dashboard"

    NotificationService.notify_deliberation_accepted(
        user_id=user_id,
        program_name=program.name,
        dashboard_url=dashboard_url,
    )

    db.session.commit()

    # Emitir actualización en tiempo real (fire-and-forget, fuera de la transaccion)
    from app.sockets.emitters import emit_to_coordinators, emit_user_and_coordinators
    try:
        from app.extensions import socketio
        socketio.emit(
            'deliberation:updated',
            {
                'user_id': public_id_service.user_uuid(user_id),
                'user_name': f'{user.first_name} {user.last_name}',
                'program_id': program_id,
                'status': 'accepted',
            },
            room=f'deliberation:{program_id}',
        )
    except Exception:
        pass

    # Eco a coordinadores del programa (no dependen del join manual a deliberation:{pid})
    emit_to_coordinators(
        'deliberation:updated',
        {
            'user_id': public_id_service.user_uuid(user_id),
            'user_name': f'{user.first_name} {user.last_name}',
            'program_id': program_id,
            'status': 'accepted',
        },
        program_id=program_id,
    )

    emit_user_and_coordinators(
        'admission:status_changed',
        {
            'user_id': public_id_service.user_uuid(user_id),
            'program_id': program_id,
            'new_status': 'accepted',
            'decision_notes': notes,
        },
        user_id=user_id,
        program_id=program_id,
    )

    return up


def _resolve_conditions(conditions, program_id: int) -> list:
    """
    [(description, archive_id|None, due_date|None)] from the request items.

    A linked requirement must be one of the conclusion requirements of
    `program_id` (the applicant's program), not any archive with the key.
    """
    from app.services import conclusion_service

    program_archives = {a.archive_key: a
                        for _, a in conclusion_service.conclusion_archives(program_id)
                        if (a.archive_key or '').startswith('conclusion_')}
    resolved = []
    for item in conditions or []:
        get = item.get if isinstance(item, dict) else (lambda k, o=item: getattr(o, k, None))
        description = (get('description') or '').strip()
        if not description:
            raise DeliberationError('Cada condición necesita una descripción.')
        archive_id = None
        key = get('archive_key')
        if key:
            archive = program_archives.get(key)
            if archive is None:
                raise DeliberationError(
                    'El requisito de conclusión indicado no existe en el programa del aspirante.')
            archive_id = archive.id
        resolved.append((description, archive_id, get('due_date')))
    return resolved


def reject_applicant(user_id: int, program_id: int, decision_by: int,
                     rejection_type: str = 'full', notes: str = None,
                     correction_required: str = None):
    """
    Rechaza a un aspirante.

    Args:
        user_id: ID del aspirante
        program_id: ID del programa
        decision_by: ID del usuario que toma la decision
        rejection_type: 'full' para rechazo total, 'partial' para solicitar correcciones
        notes: Notas sobre la decision
        correction_required: Descripcion de correcciones requeridas (solo si es partial)

    Returns:
        UserProgram actualizado
    """
    up = get_user_program_for_update(user_id, program_id)

    if up.admission_status not in ['deliberation', 'interview_completed']:
        raise InvalidStateTransition(
            f"Solo se puede rechazar desde 'deliberation' o 'interview_completed', estado actual: '{up.admission_status}'"
        )

    if rejection_type not in ['full', 'partial']:
        raise ValueError("rejection_type debe ser 'full' o 'partial'")

    up.reject(
        decision_by=decision_by,
        rejection_type=rejection_type,
        notes=notes,
        correction_required=correction_required
    )

    # Si es rechazo parcial con archive_id, marcar la submission como rechazada
    if rejection_type == 'partial' and correction_required:
        try:
            corr = json.loads(correction_required)
            archive_id = corr.get('archive_id')
            corr_notes = corr.get('notes', '')
            if archive_id:
                sub = Submission.query.join(
                    ProgramStep, Submission.program_step_id == ProgramStep.id
                ).filter(
                    Submission.user_id == user_id,
                    Submission.archive_id == archive_id,
                    ProgramStep.program_id == program_id,
                ).first()
                if sub and sub.status == 'approved':
                    sub.status = 'rejected'
                    sub.review_date = now_local()
                    sub.reviewer_id = decision_by
                    sub.reviewer_comment = corr_notes or notes
        except (json.JSONDecodeError, TypeError):
            pass

    # Obtener datos para notificacion
    user = User.query.get(user_id)
    program = Program.query.get(program_id)

    # Registrar en historial (en la misma transaccion)
    history_action = 'admission_rejected' if rejection_type == 'full' else 'correction_requested'
    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=decision_by,
        action=history_action,
        details=f'{program.name}: {notes or ""}'
    )

    # Notificar al aspirante con email (en la misma transaccion)
    # Pinned to APP_BASE_URL: this URL is embedded in an e-mail body, so it must
    # not be rebuilt from the live request host (the requester controls `Host`).
    from app.utils.urls import external_url, get_base_url
    try:
        dashboard_url = external_url('pages_user.dashboard')
    except Exception:
        # Only reachable without an application context, which neither a route
        # nor a Celery ContextTask can be. Stay absolute anyway.
        dashboard_url = f"{get_base_url()}/user/dashboard"

    NotificationService.notify_deliberation_rejected(
        user_id=user_id,
        program_name=program.name,
        rejection_type=rejection_type,
        notes=notes or '',
        dashboard_url=dashboard_url,
    )

    db.session.commit()

    # Emitir actualización en tiempo real (fire-and-forget, fuera de la transaccion)
    from app.sockets.emitters import emit_to_coordinators, emit_user_and_coordinators
    deliberation_status = rejection_type if rejection_type == 'partial' else 'rejected'
    try:
        from app.extensions import socketio
        socketio.emit(
            'deliberation:updated',
            {
                'user_id': public_id_service.user_uuid(user_id),
                'user_name': f'{user.first_name} {user.last_name}',
                'program_id': program_id,
                'status': deliberation_status,
            },
            room=f'deliberation:{program_id}',
        )
    except Exception:
        pass

    # Eco a coordinadores del programa
    emit_to_coordinators(
        'deliberation:updated',
        {
            'user_id': public_id_service.user_uuid(user_id),
            'user_name': f'{user.first_name} {user.last_name}',
            'program_id': program_id,
            'status': deliberation_status,
        },
        program_id=program_id,
    )

    emit_user_and_coordinators(
        'admission:status_changed',
        {
            'user_id': public_id_service.user_uuid(user_id),
            'program_id': program_id,
            'new_status': 'rejected',
            'rejection_type': rejection_type,
            'decision_notes': notes,
            'correction_required': correction_required,
        },
        user_id=user_id,
        program_id=program_id,
    )

    return up


def reset_to_in_progress(user_id: int, program_id: int, admin_id: int, reason: str = None):
    """
    Reinicia el estado de un aspirante a 'in_progress'.
    Usado cuando se solicitan correcciones y el aspirante las completa.

    Args:
        user_id: ID del aspirante
        program_id: ID del programa
        admin_id: ID del administrador que autoriza
        reason: Razon del reinicio

    Returns:
        UserProgram actualizado
    """
    up = get_user_program_for_update(user_id, program_id)

    if up.admission_status not in ['rejected']:
        raise InvalidStateTransition(
            f"Solo se puede reiniciar desde 'rejected', estado actual: '{up.admission_status}'"
        )

    if up.rejection_type != 'partial':
        raise InvalidStateTransition(
            "Solo se puede reiniciar cuando el rechazo fue parcial (solicitud de correccion)"
        )

    # Reiniciar estado
    _move_to(up, 'in_progress')
    up.deliberation_started_at = None
    up.decision_at = None
    up.decision_by = None
    up.decision_notes = None
    up.rejection_type = None
    up.correction_required = None

    # Registrar en historial (en la misma transaccion)
    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=admin_id,
        action='admission_reset',
        details=f'Estado reiniciado a in_progress. {reason or ""}'
    )

    # Notificar al aspirante
    program = Program.query.get(program_id)
    program_name = program.name if program else 'tu programa'
    NotificationService.create_notification(
        user_id=user_id,
        notification_type='deliberation_reset',
        title='Tu expediente fue reabierto',
        message=f'Tu expediente en {program_name} ha sido reabierto para que realices las correcciones solicitadas. '
                f'Revisa tu portal para ver los documentos que necesitan ajustes.',
        priority='high',
        action_url=f'/programs/admission/{program.slug}' if program else '/user/dashboard',
    )

    db.session.commit()

    # Notificar al aspirante + coordinadores del programa en tiempo real
    from app.sockets.emitters import emit_user_and_coordinators
    emit_user_and_coordinators(
        'admission:status_changed',
        {
            'user_id': public_id_service.user_uuid(user_id),
            'program_id': program_id,
            'new_status': 'in_progress',
        },
        user_id=user_id,
        program_id=program_id,
    )

    return up


def force_reset_applicant(user_id: int, program_id: int, admin_id: int, reason: str = None):
    """
    Reinicia forzosamente el estado de un aspirante a 'in_progress' desde cualquier
    estado salvo 'enrolled' (terminal: un alumno inscrito no se puede reiniciar).
    Solo debe ser usado por postgraduate_admin para correcciones administrativas.

    Args:
        user_id: ID del aspirante
        program_id: ID del programa
        admin_id: ID del admin que autoriza
        reason: Razón del reinicio

    Returns:
        UserProgram actualizado

    Raises:
        InvalidStateTransition: Si el aspirante ya esta inscrito.
    """
    up = get_user_program_for_update(user_id, program_id)

    prev_status = up.admission_status
    # Raises before anything is cleared when the move is refused (an `enrolled`
    # student is terminal and cannot be reset).
    _move_to(up, 'in_progress')
    up.deliberation_started_at = None
    up.decision_at = None
    up.decision_by = None
    up.decision_notes = None
    up.rejection_type = None
    up.correction_required = None

    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=admin_id,
        action='admission_reset',
        details=f'Reinicio administrativo forzado desde "{prev_status}". {reason or ""}'
    )

    # Notificar al aspirante
    program = Program.query.get(program_id)
    program_name = program.name if program else 'tu programa'
    NotificationService.create_notification(
        user_id=user_id,
        notification_type='deliberation_reset',
        title='Tu expediente fue reiniciado',
        message=f'Tu expediente en {program_name} ha sido reiniciado por un administrador. '
                f'{("Motivo: " + reason) if reason else "Revisa tu portal para más detalles."}',
        priority='high',
        action_url=f'/programs/admission/{program.slug}' if program else '/user/dashboard',
    )

    db.session.commit()

    # Notificar al aspirante + coordinadores del programa en tiempo real
    from app.sockets.emitters import emit_user_and_coordinators
    emit_user_and_coordinators(
        'admission:status_changed',
        {
            'user_id': public_id_service.user_uuid(user_id),
            'program_id': program_id,
            'new_status': 'in_progress',
            'forced_reset': True,
        },
        user_id=user_id,
        program_id=program_id,
    )

    return up


def get_deliberation_stats(program_id: int):
    """
    Obtiene estadisticas de deliberacion para un programa.

    Args:
        program_id: ID del programa

    Returns:
        Dict con conteos por estado
    """
    from sqlalchemy import func

    stats = db.session.query(
        UserProgram.admission_status,
        func.count(UserProgram.id)
    ).filter(
        UserProgram.program_id == program_id
    ).group_by(
        UserProgram.admission_status
    ).all()

    result = {
        'in_progress': 0,
        'interview_completed': 0,
        'deliberation': 0,
        'accepted': 0,
        'rejected': 0,
        'deferred': 0,
        'enrolled': 0,
        'total': 0
    }

    for status, count in stats:
        if status in result:
            result[status] = count
            result['total'] += count

    return result


def get_applicants_with_pending_interview(program_id: int):
    """
    Obtiene aspirantes que tienen una cita de entrevista agendada (Appointment)
    pero aun estan en 'in_progress'. Estos son candidatos para marcar como
    'interview_completed' cuando se complete la entrevista.

    Args:
        program_id: ID del programa

    Returns:
        Lista de UserProgram con entrevista pendiente de marcar
    """
    from app.models.event import Event, EventSlot, EventWindow
    from app.models.appointment import Appointment

    # Obtener aspirantes que tienen una cita de entrevista agendada (scheduled)
    # Se incluyen tanto eventos del programa como eventos globales (program_id=NULL)
    # ya que la asociación con el programa se verifica mediante UserProgram
    subquery_appointments = db.session.query(Appointment.applicant_id).join(
        Event, Appointment.event_id == Event.id
    ).filter(
        or_(Event.program_id == program_id, Event.program_id.is_(None)),
        Event.type == 'interview',
        Appointment.status == 'scheduled'
    ).subquery()

    # Obtener UserPrograms en in_progress que tienen cita agendada (excluye desactivados)
    applicants = UserProgram.query.join(
        User, UserProgram.user_id == User.id
    ).filter(
        UserProgram.program_id == program_id,
        UserProgram.admission_status == 'in_progress',
        UserProgram.user_id.in_(subquery_appointments),
        User.is_active == True,  # noqa: E712
    ).order_by(UserProgram.updated_at.desc()).all()

    return applicants


def list_admission_archives(program_id: int) -> list:
    """Uploadable archives of the admission phase of a program (partial rejection)."""
    from sqlalchemy import and_
    from app.models import Step, ProgramStep, Phase
    from app.models.archive import Archive

    return (
        Archive.query
        .join(Step, Archive.step_id == Step.id)
        .join(ProgramStep, Step.id == ProgramStep.step_id)
        .join(Phase, Step.phase_id == Phase.id)
        .filter(
            and_(
                ProgramStep.program_id == program_id,
                Phase.name == 'admission',
                Archive.is_uploadable == True  # noqa: E712
            )
        )
        .order_by(ProgramStep.sequence, Archive.id)
        .all()
    )


def list_conclusion_requirements(program_ids) -> dict:
    """
    {program_id: [{'key', 'name'}]} — the conclusion requirements a condition
    can point to, per program (the acceptance modal is per applicant, and the
    applicant's program decides which requirements exist).
    """
    from app.services import conclusion_service

    options = {}
    for program_id in program_ids or []:
        seen, rows = set(), []
        for _, archive in conclusion_service.conclusion_archives(program_id):
            key = archive.archive_key or ''
            if not key.startswith('conclusion_') or key in seen:
                continue
            seen.add(archive.archive_key)
            rows.append({'key': archive.archive_key, 'name': archive.name})
        options[program_id] = rows
    return options

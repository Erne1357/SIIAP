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
"""

from app import db
from app.models import UserProgram, User, Program
from app.services.notification_service import NotificationService
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local
from sqlalchemy import and_


class DeliberationError(Exception):
    """Error base para operaciones de deliberacion."""
    pass


class ApplicantNotFound(DeliberationError):
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
            UserProgram.admission_status.in_(['interview_completed', 'deliberation'])
        )
    ).order_by(UserProgram.deliberation_started_at.desc()).all()


def get_applicants_by_status(program_id: int, status: str):
    """
    Obtiene aspirantes de un programa por estado de admision.

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
            UserProgram.admission_status == status
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
        raise ApplicantNotFound(f"No se encontro al aspirante {user_id} en el programa {program_id}")

    return up


def mark_interview_completed(user_id: int, program_id: int):
    """
    Marca que el aspirante completo su entrevista.
    Esto lo prepara para entrar en deliberacion.
    Tambien marca la cita (Appointment) como 'done' si existe.

    Args:
        user_id: ID del usuario
        program_id: ID del programa

    Returns:
        UserProgram actualizado
    """
    from app.models.appointment import Appointment
    from app.models.event import Event

    up = get_user_program(user_id, program_id)

    if up.admission_status not in ['in_progress']:
        raise InvalidStateTransition(
            f"No se puede marcar entrevista completada desde estado '{up.admission_status}'"
        )

    up.admission_status = 'interview_completed'

    # Buscar y marcar la cita de entrevista como 'done'
    appointment = Appointment.query.join(
        Event, Appointment.event_id == Event.id
    ).filter(
        Appointment.applicant_id == user_id,
        Event.program_id == program_id,
        Event.type == 'interview',
        Appointment.status == 'scheduled'
    ).first()

    if appointment:
        appointment.status = 'done'

    db.session.commit()

    return up


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
    up = get_user_program(user_id, program_id)

    if up.admission_status not in ['interview_completed']:
        raise InvalidStateTransition(
            f"Solo se puede iniciar deliberacion desde 'interview_completed', estado actual: '{up.admission_status}'"
        )

    up.start_deliberation()
    db.session.commit()

    # Registrar en historial
    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=coordinator_id,
        action='deliberation_started',
        details='Proceso de deliberacion iniciado'
    )

    return up


def accept_applicant(user_id: int, program_id: int, decision_by: int, notes: str = None):
    """
    Acepta a un aspirante en el programa.

    Args:
        user_id: ID del aspirante
        program_id: ID del programa
        decision_by: ID del usuario que toma la decision
        notes: Notas opcionales sobre la decision

    Returns:
        UserProgram actualizado
    """
    up = get_user_program(user_id, program_id)

    if up.admission_status not in ['deliberation', 'interview_completed']:
        raise InvalidStateTransition(
            f"Solo se puede aceptar desde 'deliberation' o 'interview_completed', estado actual: '{up.admission_status}'"
        )

    up.accept(decision_by=decision_by, notes=notes)
    db.session.commit()

    # Obtener datos para notificacion
    user = User.query.get(user_id)
    program = Program.query.get(program_id)

    # Registrar en historial
    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=decision_by,
        action='admission_accepted',
        details=f'Aceptado en {program.name}. {notes or ""}'
    )

    # Notificar al aspirante
    NotificationService.send(
        user_id=user_id,
        title='Felicidades! Has sido aceptado',
        message=f'Has sido aceptado en el programa {program.name}. Revisa tu correo para mas informacion.'
    )

    return up


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
    up = get_user_program(user_id, program_id)

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
    db.session.commit()

    # Obtener datos para notificacion
    user = User.query.get(user_id)
    program = Program.query.get(program_id)

    # Registrar en historial
    action = 'admission_rejected' if rejection_type == 'full' else 'correction_requested'
    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=decision_by,
        action=action,
        details=f'{program.name}: {notes or ""}'
    )

    # Notificar al aspirante
    if rejection_type == 'full':
        NotificationService.send(
            user_id=user_id,
            title='Resultado de tu proceso de admision',
            message=f'Lamentamos informarte que no has sido aceptado en el programa {program.name}. Consulta tu correo para mas detalles.'
        )
    else:
        NotificationService.send(
            user_id=user_id,
            title='Se requieren correcciones en tu expediente',
            message=f'El comite de admision de {program.name} ha solicitado algunas correcciones. Revisa los detalles en tu portal.'
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
    up = get_user_program(user_id, program_id)

    if up.admission_status not in ['rejected']:
        raise InvalidStateTransition(
            f"Solo se puede reiniciar desde 'rejected', estado actual: '{up.admission_status}'"
        )

    if up.rejection_type != 'partial':
        raise InvalidStateTransition(
            "Solo se puede reiniciar cuando el rechazo fue parcial (solicitud de correccion)"
        )

    # Reiniciar estado
    up.admission_status = 'in_progress'
    up.deliberation_started_at = None
    up.decision_at = None
    up.decision_by = None
    up.decision_notes = None
    up.rejection_type = None
    up.correction_required = None
    db.session.commit()

    # Registrar en historial
    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=admin_id,
        action='admission_reset',
        details=f'Estado reiniciado a in_progress. {reason or ""}'
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
    # para un evento de tipo 'interview' del programa
    subquery_appointments = db.session.query(Appointment.applicant_id).join(
        Event, Appointment.event_id == Event.id
    ).filter(
        Event.program_id == program_id,
        Event.type == 'interview',
        Appointment.status == 'scheduled'
    ).subquery()

    # Obtener UserPrograms en in_progress que tienen cita agendada
    applicants = UserProgram.query.join(
        User, UserProgram.user_id == User.id
    ).filter(
        UserProgram.program_id == program_id,
        UserProgram.admission_status == 'in_progress',
        UserProgram.user_id.in_(subquery_appointments)
    ).order_by(UserProgram.updated_at.desc()).all()

    return applicants

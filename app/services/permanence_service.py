# app/services/permanence_service.py
"""
Servicio para gestionar la permanencia semestral de estudiantes (Fase 6).

Flujo por semestre:
1. Coordinador confirma que el estudiante se inscribio/pago en el nuevo periodo
2. Se crea un SemesterEnrollment con status='active' y se incrementa current_semester
3. El estudiante ve su estado en su dashboard
4. Al terminar el semestre, el coordinador puede marcarlo como 'completed'
"""

from app import db
from app.models import UserProgram, User, Program, AcademicPeriod
from app.models.semester_enrollment import SemesterEnrollment
from app.services.notification_service import NotificationService
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local
from sqlalchemy import and_


class PermanenceError(Exception):
    """Error base para operaciones de permanencia."""
    pass


class StudentNotFound(PermanenceError):
    pass


class InvalidStateTransition(PermanenceError):
    pass


def get_enrolled_students(program_id: int) -> list:
    """
    Obtiene todos los estudiantes inscritos de un programa con su estado
    de permanencia para el periodo activo.

    Returns:
        Lista de dicts con user, user_program, current_enrollment, history
    """
    active_period = AcademicPeriod.get_active_period()

    user_programs = (
        UserProgram.query
        .join(User, UserProgram.user_id == User.id)
        .filter(
            and_(
                UserProgram.program_id == program_id,
                UserProgram.admission_status == 'enrolled',
            )
        )
        .order_by(User.last_name, User.first_name)
        .all()
    )

    result = []
    for up in user_programs:
        user = up.user

        # Inscripcion semestral para el periodo activo
        current_enrollment = None
        if active_period:
            current_enrollment = SemesterEnrollment.query.filter_by(
                user_program_id=up.id,
                academic_period_id=active_period.id
            ).first()

        # Historial de semestres (todos los periodos)
        history = (
            SemesterEnrollment.query
            .filter_by(user_program_id=up.id)
            .join(AcademicPeriod, SemesterEnrollment.academic_period_id == AcademicPeriod.id)
            .order_by(SemesterEnrollment.semester_number)
            .all()
        )

        result.append({
            'user_program': up.to_dict(),
            'user': {
                'id': user.id,
                'full_name': f"{user.first_name} {user.last_name} {user.mother_last_name or ''}".strip(),
                'email': user.email,
                'control_number': user.control_number,
            },
            'current_enrollment': current_enrollment.to_dict() if current_enrollment else None,
            'current_period': active_period.to_dict() if active_period else None,
            'history': [
                {
                    **se.to_dict(),
                    'period_name': se.academic_period.name,
                    'period_code': se.academic_period.code,
                }
                for se in history
            ],
        })

    return result


def get_permanence_stats(program_id: int) -> dict:
    """
    Estadisticas de permanencia para un programa.

    Returns:
        Dict con conteos: total_students, confirmed, pending, on_leave
    """
    active_period = AcademicPeriod.get_active_period()

    total_students = UserProgram.query.filter_by(
        program_id=program_id,
        admission_status='enrolled'
    ).count()

    if not active_period:
        return {
            'total_students': total_students,
            'confirmed': 0,
            'pending': total_students,
            'on_leave': 0,
            'has_active_period': False,
        }

    ups = UserProgram.query.filter_by(
        program_id=program_id,
        admission_status='enrolled'
    ).all()

    confirmed = 0
    on_leave = 0
    for up in ups:
        se = SemesterEnrollment.query.filter_by(
            user_program_id=up.id,
            academic_period_id=active_period.id
        ).first()
        if se and se.enrollment_confirmed:
            confirmed += 1
        elif se and se.status == 'on_leave':
            on_leave += 1

    return {
        'total_students': total_students,
        'confirmed': confirmed,
        'pending': total_students - confirmed - on_leave,
        'on_leave': on_leave,
        'has_active_period': True,
        'active_period_name': active_period.name,
    }


def confirm_semester_enrollment(
    user_program_id: int,
    academic_period_id: int,
    coordinator_id: int,
    notes: str = None
) -> SemesterEnrollment:
    """
    El coordinador confirma la inscripcion semestral de un estudiante.

    Si no existe un SemesterEnrollment para este user_program + periodo, lo crea.
    Incrementa current_semester en UserProgram solo si es un periodo nuevo.

    Returns:
        SemesterEnrollment actualizado/creado
    """
    up = UserProgram.query.get(user_program_id)
    if not up:
        raise StudentNotFound(f"UserProgram {user_program_id} no encontrado")

    if up.admission_status != 'enrolled':
        raise InvalidStateTransition(
            f"Solo estudiantes inscritos pueden tener permanencia semestral. "
            f"Estado actual: '{up.admission_status}'"
        )

    period = AcademicPeriod.query.get(academic_period_id)
    if not period:
        raise StudentNotFound(f"Periodo academico {academic_period_id} no encontrado")

    # Verificar si ya existe inscripcion para este periodo
    se = SemesterEnrollment.query.filter_by(
        user_program_id=user_program_id,
        academic_period_id=academic_period_id
    ).first()

    is_new = se is None

    if se and se.enrollment_confirmed:
        raise InvalidStateTransition(
            "La inscripcion semestral ya fue confirmada para este periodo"
        )

    if is_new:
        # Calcular el numero de semestre: uno mas que el maximo registrado
        max_sem = db.session.query(
            db.func.max(SemesterEnrollment.semester_number)
        ).filter_by(user_program_id=user_program_id).scalar() or 0

        semester_number = max_sem + 1

        se = SemesterEnrollment(
            user_program_id=user_program_id,
            academic_period_id=academic_period_id,
            semester_number=semester_number,
            status='active',
        )
        db.session.add(se)

        # Actualizar el semestre actual en user_program
        up.current_semester = semester_number
    else:
        se.status = 'active'

    se.enrollment_confirmed = True
    se.confirmed_by = coordinator_id
    se.confirmed_at = now_local()
    se.notes = notes

    user = up.user
    program = up.program

    # Notificar al estudiante
    NotificationService.create_notification(
        user_id=user.id,
        notification_type='semester_enrolled',
        title=f'Inscripción confirmada — {period.name}',
        message=(
            f'Tu inscripción para el semestre {se.semester_number} '
            f'({period.name}) ha sido confirmada. '
            f'Puedes ver tu estado en tu panel de permanencia.'
        ),
        priority='medium',
        action_url='/user/dashboard',
    )

    UserHistoryService.log_action(
        user_id=coordinator_id,
        admin_id=coordinator_id,
        action='semester_enrollment_confirmed',
        details=(
            f'Confirmó semestre {se.semester_number} de '
            f'{user.first_name} {user.last_name} en {program.name} '
            f'para el periodo {period.name}'
        )
    )

    db.session.commit()
    return se


def update_enrollment_status(
    semester_enrollment_id: int,
    new_status: str,
    coordinator_id: int,
    notes: str = None
) -> SemesterEnrollment:
    """
    Actualiza el estado de una inscripcion semestral.

    Estados validos: active, completed, on_leave, dropped
    """
    VALID_STATUSES = {'active', 'completed', 'on_leave', 'dropped'}
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Estado invalido: '{new_status}'. Use: {', '.join(VALID_STATUSES)}")

    se = SemesterEnrollment.query.get(semester_enrollment_id)
    if not se:
        raise StudentNotFound(f"Inscripcion semestral {semester_enrollment_id} no encontrada")

    old_status = se.status
    se.status = new_status
    if notes:
        se.notes = notes
    se.updated_at = now_local()

    up = se.user_program
    user = up.user
    program = up.program
    period = se.academic_period

    STATUS_LABELS = {
        'active': 'Activo',
        'completed': 'Completado',
        'on_leave': 'Baja temporal',
        'dropped': 'Baja definitiva',
    }

    UserHistoryService.log_action(
        user_id=coordinator_id,
        admin_id=coordinator_id,
        action='semester_enrollment_status_updated',
        details=(
            f'Cambió estado de semestre {se.semester_number} de '
            f'{user.first_name} {user.last_name} en {program.name} '
            f'({period.name}): {STATUS_LABELS.get(old_status, old_status)} → '
            f'{STATUS_LABELS.get(new_status, new_status)}'
        )
    )

    # Notificar al estudiante solo en estados finales significativos
    NOTIFY_STATUSES = {
        'completed': ('Semestre completado', f'Tu semestre {se.semester_number} ({period.name}) en {program.name} ha sido marcado como completado.'),
        'on_leave': ('Baja temporal registrada', f'Se ha registrado una baja temporal en tu semestre {se.semester_number} ({period.name}) en {program.name}.'),
        'dropped': ('Baja definitiva registrada', f'Se ha registrado una baja definitiva en tu semestre {se.semester_number} ({period.name}) en {program.name}. Contacta al coordinador si crees que esto es un error.'),
    }

    if new_status in NOTIFY_STATUSES:
        title, message = NOTIFY_STATUSES[new_status]
        priority = 'high' if new_status == 'dropped' else 'medium'
        NotificationService.create_notification(
            user_id=user.id,
            notification_type='enrollment_status_changed',
            title=title,
            message=message,
            priority=priority,
            action_url='/user/dashboard',
        )

    db.session.commit()
    return se


def get_student_permanence(user_program_id: int) -> dict:
    """
    Obtiene el estado de permanencia de un estudiante para mostrarlo en su dashboard.

    Returns:
        Dict con current_enrollment, current_period, history
    """
    up = UserProgram.query.get(user_program_id)
    if not up:
        raise StudentNotFound(f"UserProgram {user_program_id} no encontrado")

    active_period = AcademicPeriod.get_active_period()

    current_enrollment = None
    if active_period:
        current_enrollment = SemesterEnrollment.query.filter_by(
            user_program_id=user_program_id,
            academic_period_id=active_period.id
        ).first()

    history = (
        SemesterEnrollment.query
        .filter_by(user_program_id=user_program_id)
        .join(AcademicPeriod, SemesterEnrollment.academic_period_id == AcademicPeriod.id)
        .order_by(SemesterEnrollment.semester_number)
        .all()
    )

    return {
        'user_program': up.to_dict(),
        'current_semester': max((se.semester_number for se in history), default=up.current_semester),
        'current_enrollment': current_enrollment.to_dict() if current_enrollment else None,
        'current_period': active_period.to_dict() if active_period else None,
        'history': [
            {
                **se.to_dict(),
                'period_name': se.academic_period.name,
                'period_code': se.academic_period.code,
            }
            for se in history
        ],
    }

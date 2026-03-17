"""
Tareas Celery para el envío masivo de notificaciones y correos.

Uso desde cualquier servicio Flask:
    from app.tasks.notifications import send_bulk_notification

    # Enviar a una lista de user_ids
    send_bulk_notification.delay(
        user_ids=[1, 2, 3],
        notification_type='event_announcement',
        title='Nuevo evento',
        message='Te invitamos al taller de tesis el viernes.',
        action_url='/events/42',
        priority='high',
    )

    # Enviar a un rol completo
    send_bulk_notification_by_filter.delay(
        filter_type='role',
        filter_value='applicant',
        notification_type='deadline_reminder',
        title='Recordatorio de fecha límite',
        message='Tu proceso de admisión vence en 7 días.',
        priority='high',
    )
"""

import logging
from typing import List, Optional

from app.celery_app import celery

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. ENVÍO MASIVO POR LISTA DE USER IDs
# ─────────────────────────────────────────────────────────────────────────────

@celery.task(
    name='app.tasks.notifications.send_bulk_notification',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_bulk_notification(
    self,
    user_ids: List[int],
    notification_type: str,
    title: str,
    message: str,
    priority: str = 'medium',
    action_url: Optional[str] = None,
    data: Optional[dict] = None,
    send_email: bool = False,
    email_subject: Optional[str] = None,
    email_html: Optional[str] = None,
):
    """
    Crea notificaciones in-app para cada user_id de la lista.

    Args:
        user_ids:          IDs de los usuarios destinatarios.
        notification_type: Tipo de notificación (ej. 'event_announcement').
        title:             Título de la notificación.
        message:           Texto del mensaje.
        priority:          'low' | 'medium' | 'high' | 'critical'
        action_url:        URL a la que lleva el botón de acción (ej. '/events/42').
        data:              JSON extra que quieras adjuntar.
        send_email:        Si True, también encola un correo para cada usuario.
        email_subject:     Asunto del correo (requerido si send_email=True).
        email_html:        HTML del correo (requerido si send_email=True).
    """
    from app import db
    from app.services.notification_service import NotificationService
    from app.models.user import User

    logger.info(
        f"[send_bulk_notification] Enviando '{title}' a {len(user_ids)} usuarios..."
    )

    created = 0
    errors = 0

    try:
        for uid in user_ids:
            try:
                NotificationService.create_notification(
                    user_id=uid,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    priority=priority,
                    action_url=action_url,
                    data=data or {},
                )
                created += 1

                if send_email and email_subject and email_html:
                    try:
                        from app.services.email_service import EmailService
                        EmailService.queue_email(uid, email_subject, email_html)
                    except Exception as e:
                        logger.warning(f"Error al encolar correo para user {uid}: {e}")

            except Exception as e:
                errors += 1
                logger.warning(f"Error creando notificación para user {uid}: {e}")

        db.session.commit()

        logger.info(
            f"[send_bulk_notification] Completado. Creadas: {created}, errores: {errors}"
        )
        return {'created': created, 'errors': errors}

    except Exception as exc:
        db.session.rollback()
        logger.error(f"[send_bulk_notification] Error fatal: {exc}", exc_info=True)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# 2. ENVÍO MASIVO POR FILTRO (rol, programa, proceso, etc.)
# ─────────────────────────────────────────────────────────────────────────────

@celery.task(
    name='app.tasks.notifications.send_bulk_notification_by_filter',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_bulk_notification_by_filter(
    self,
    filter_type: str,
    filter_value: str,
    notification_type: str,
    title: str,
    message: str,
    priority: str = 'medium',
    action_url: Optional[str] = None,
    data: Optional[dict] = None,
    send_email: bool = False,
    email_subject: Optional[str] = None,
    email_html: Optional[str] = None,
):
    """
    Resuelve la lista de user_ids según el filtro y delega a send_bulk_notification.

    filter_type puede ser:
      'role'      → filter_value = nombre del rol (ej. 'applicant')
      'program'   → filter_value = slug o id del programa
      'process'   → filter_value = estado del proceso (ej. 'in_progress')
      'all'       → notifica a todos los usuarios activos (filter_value ignorado)

    Ejemplo:
        send_bulk_notification_by_filter.delay(
            filter_type='role',
            filter_value='applicant',
            notification_type='deadline_reminder',
            title='Recordatorio',
            message='Tu proceso vence pronto.',
            action_url='/user/dashboard',
        )
    """
    from app.models.user import User
    from app.models.role import Role
    from app.models.user_program import UserProgram

    logger.info(
        f"[send_bulk_notification_by_filter] "
        f"Resolviendo filtro '{filter_type}={filter_value}'..."
    )

    try:
        user_ids = []

        if filter_type == 'role':
            role = Role.query.filter_by(name=filter_value).first()
            if role:
                users = User.query.filter(
                    User.roles.any(id=role.id),
                    User.is_active == True,
                ).all()
                user_ids = [u.id for u in users]

        elif filter_type == 'program':
            ups = UserProgram.query.filter_by(program_id=filter_value).all()
            user_ids = list({up.user_id for up in ups})

        elif filter_type == 'process':
            ups = UserProgram.query.filter_by(status=filter_value).all()
            user_ids = list({up.user_id for up in ups})

        elif filter_type == 'all':
            users = User.query.filter_by(is_active=True).all()
            user_ids = [u.id for u in users]

        else:
            logger.warning(f"filter_type desconocido: {filter_type}")
            return {'error': f'filter_type desconocido: {filter_type}'}

        logger.info(
            f"[send_bulk_notification_by_filter] "
            f"Encontrados {len(user_ids)} usuarios. Delegando a send_bulk_notification..."
        )

        # Delega el envío real a la tarea por lista
        send_bulk_notification.delay(
            user_ids=user_ids,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            action_url=action_url,
            data=data,
            send_email=send_email,
            email_subject=email_subject,
            email_html=email_html,
        )

        return {'user_ids_resolved': len(user_ids), 'filter': f'{filter_type}={filter_value}'}

    except Exception as exc:
        logger.error(
            f"[send_bulk_notification_by_filter] Error: {exc}", exc_info=True
        )
        raise self.retry(exc=exc)

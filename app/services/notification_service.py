from app import db
from app.models.notification import Notification
from app.models.user import User
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.utils.datetime_utils import now_local
from flask import url_for


class NotificationService:
    """
    Servicio centralizado para gestionar notificaciones del sistema.
    """
    
    # Tipos de notificaciones que requieren acción del usuario
    ACTIONABLE_TYPES = {
        'document_rejected',
        'extension_rejected',
        'event_invitation',
        'password_reset',
        'profile_incomplete',
        'extension_deadline_near'
    }
    
    @staticmethod
    def create_notification(
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        priority: str = 'medium',
        data: Optional[Dict[str, Any]] = None,
        related_invitation_id: Optional[int] = None,
        expires_at: Optional[datetime] = None
    ) -> Notification:
        """
        Crea una notificación para un usuario.
        
        Args:
            user_id: ID del usuario que recibirá la notificación
            notification_type: Tipo de notificación
            title: Título de la notificación
            message: Mensaje de la notificación
            priority: Prioridad (low, medium, high, critical)
            data: Datos adicionales en formato JSON
            related_invitation_id: ID de invitación relacionada (si aplica)
            expires_at: Fecha de expiración (opcional)
        """
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            priority=priority,
            data=data or {},
            related_invitation_id=related_invitation_id,
            expires_at=expires_at,
            is_actionable=notification_type in NotificationService.ACTIONABLE_TYPES
        )
        
        db.session.add(notification)
        db.session.flush()
        return notification
    
    # ==================== DOCUMENTOS ====================
    
    @staticmethod
    def notify_document_approved(user_id: int, archive_name: str, submission_id: int) -> Notification:
        """Notifica cuando un documento es aprobado"""
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='document_approved',
            title='Documento aprobado',
            message=f'Tu documento "{archive_name}" ha sido aprobado.',
            priority='medium',
            data={
                'submission_id': submission_id,
                'archive_name': archive_name,
                'url': '/user/dashboard'
            }
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('program.admission.admission_dashboard', 
                                       slug=user.user_program[0].program.slug if user.user_program else 'general', 
                                       _external=True)
                subject, html = EmailTemplates.document_approved(
                    user_name=f"{user.first_name} {user.last_name}",
                    archive_name=archive_name,
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for document_approved: {e}")
        
        return notification
    
    @staticmethod
    def notify_document_rejected(user_id: int, archive_name: str, submission_id: int, reason: str = None) -> Notification:
        """Notifica cuando un documento es rechazado"""
        message = f'Tu documento "{archive_name}" fue rechazado.'
        if reason:
            message += f' Motivo: {reason}'
        
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='document_rejected',
            title='Documento rechazado',
            message=message,
            priority='high',
            data={
                'submission_id': submission_id,
                'archive_name': archive_name,
                'reason': reason,
                'url': '/user/dashboard'
            }
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('program.admission.admission_dashboard', 
                                       slug=user.user_program[0].program.slug if user.user_program else 'general', 
                                       _external=True)
                subject, html = EmailTemplates.document_rejected(
                    user_name=f"{user.first_name} {user.last_name}",
                    archive_name=archive_name,
                    reason=reason or "No especificado",
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for document_rejected: {e}")
        
        return notification
    
    @staticmethod
    def notify_coordinator_uploaded(user_id: int, archive_name: str, submission_id: int, coordinator_name: str) -> Notification:
        """Notifica cuando el coordinador sube un documento por el estudiante"""
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='coordinator_uploaded',
            title='Documento subido por coordinador',
            message=f'El coordinador {coordinator_name} ha subido el documento "{archive_name}" por ti.',
            priority='medium',
            data={
                'submission_id': submission_id,
                'archive_name': archive_name,
                'url': '/user/dashboard'
            }
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('program.admission.admission_dashboard', 
                                       slug=user.user_program[0].program.slug if user.user_program else 'general', 
                                       _external=True)
                subject, html = EmailTemplates.coordinator_uploaded(
                    user_name=f"{user.first_name} {user.last_name}",
                    archive_name=archive_name,
                    coordinator_name=coordinator_name,
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for coordinator_uploaded: {e}")
        
        return notification
    
    # ==================== PRÓRROGAS ====================
    
    @staticmethod
    def notify_extension_approved(user_id: int, archive_name: str, granted_until: str) -> Notification:
        """Notifica cuando una prórroga es aprobada"""
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='extension_approved',
            title='Prórroga aprobada',
            message=f'Tu solicitud de prórroga para "{archive_name}" ha sido aprobada hasta el {granted_until}.',
            priority='medium',
            data={
                'archive_name': archive_name,
                'granted_until': granted_until,
                'url': '/user/dashboard'
            }
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('program.admission.admission_dashboard', 
                                       slug=user.user_program[0].program.slug if user.user_program else 'general', 
                                       _external=True)
                subject, html = EmailTemplates.extension_approved(
                    user_name=f"{user.first_name} {user.last_name}",
                    archive_name=archive_name,
                    granted_until=granted_until,
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for extension_approved: {e}")
        
        return notification
    
    @staticmethod
    def notify_extension_rejected(user_id: int, archive_name: str, reason: str = None) -> Notification:
        """Notifica cuando una prórroga es rechazada"""
        message = f'Tu solicitud de prórroga para "{archive_name}" ha sido rechazada.'
        if reason:
            message += f' Motivo: {reason}'
        
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='extension_rejected',
            title='Prórroga rechazada',
            message=message,
            priority='high',
            data={
                'archive_name': archive_name,
                'reason': reason,
                'url': '/user/dashboard'
            }
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('program.admission.admission_dashboard', 
                                       slug=user.user_program[0].program.slug if user.user_program else 'general', 
                                       _external=True)
                subject, html = EmailTemplates.extension_rejected(
                    user_name=f"{user.first_name} {user.last_name}",
                    archive_name=archive_name,
                    reason=reason or "No especificado",
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for extension_rejected: {e}")
        
        return notification
    
    # ==================== EVENTOS Y CITAS ====================
    
    @staticmethod
    def notify_appointment_assigned(user_id: int, event_title: str, appointment_id: int, 
                                   slot_datetime: str, event_id: int, location: str = None) -> Notification:
        """Notifica cuando se asigna una cita"""
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='appointment_assigned',
            title='Cita asignada',
            message=f'Se te ha asignado una cita para "{event_title}" el {slot_datetime}.',
            priority='high',
            data={
                'appointment_id': appointment_id,
                'event_id': event_id,
                'event_title': event_title,
                'slot_datetime': slot_datetime,
                'url': '/events/'
            }
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('pages_user.dashboard', _external=True)
                subject, html = EmailTemplates.appointment_assigned(
                    user_name=f"{user.first_name} {user.last_name}",
                    event_title=event_title,
                    slot_datetime=slot_datetime,
                    location=location or "Por confirmar",
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for appointment_assigned: {e}")
        
        return notification
    
    @staticmethod
    def notify_appointment_cancelled(user_id: int, event_title: str, reason: str) -> Notification:
        """Notifica cuando se cancela una cita"""
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='appointment_cancelled',
            title='Cita cancelada',
            message=f'Tu cita para "{event_title}" ha sido cancelada. Motivo: {reason}',
            priority='high',
            data={
                'event_title': event_title,
                'reason': reason,
                'url': '/events/'
            }
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('pages_user.dashboard', _external=True)
                subject, html = EmailTemplates.appointment_cancelled(
                    user_name=f"{user.first_name} {user.last_name}",
                    event_title=event_title,
                    reason=reason,
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for appointment_cancelled: {e}")
        
        return notification
    
    @staticmethod
    def notify_event_invitation(user_id: int, event_title: str, event_id: int, 
                               invitation_id: int, event_date: str, description: str = None) -> Notification:
        """Notifica sobre una invitación a evento"""
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='event_invitation',
            title='Invitación a evento',
            message=f'Has sido invitado a "{event_title}" el {event_date}.',
            priority='high',
            data={
                'event_id': event_id,
                'invitation_id': invitation_id,
                'event_title': event_title,
                'event_date': event_date,
                'url': '/events/'
            },
            related_invitation_id=invitation_id
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                event_url = url_for('pages_events_public.view_event', event_id=event_id, _external=True)
                subject, html = EmailTemplates.event_invitation(
                    user_name=f"{user.first_name} {user.last_name}",
                    event_title=event_title,
                    event_date=event_date,
                    description=description or "Evento importante del sistema de posgrado",
                    event_url=event_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for event_invitation: {e}")
        
        return notification
    
    # ==================== ADMINISTRATIVAS ====================
    
    @staticmethod
    def notify_password_reset(user_id: int) -> Notification:
        """Notifica cuando la contraseña es reseteada por un admin"""
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='password_reset',
            title='Contraseña reseteada',
            message='Tu contraseña ha sido reseteada a "tecno#2K". Debes cambiarla en tu próximo inicio de sesión.',
            priority='critical',
            data={'url': '/user/profile'}
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('pages_auth.login_page', _external=True)
                subject, html = EmailTemplates.password_reset(
                    user_name=f"{user.first_name} {user.last_name}",
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for password_reset: {e}")
        
        return notification
    
    @staticmethod
    def notify_control_number_assigned(user_id: int, control_number: str) -> Notification:
        """Notifica cuando se asigna un número de control"""
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='control_number_assigned',
            title='Número de control asignado',
            message=f'Se te ha asignado el número de control: {control_number}',
            priority='high',
            data={
                'control_number': control_number,
                'url': '/user/profile'
            }
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('pages_user.profile', _external=True)
                subject, html = EmailTemplates.control_number_assigned(
                    user_name=f"{user.first_name} {user.last_name}",
                    control_number=control_number,
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for control_number_assigned: {e}")
        
        return notification
    
    @staticmethod
    def notify_account_deactivated(user_id: int, reason: str = None) -> Notification:
        """Notifica cuando una cuenta es desactivada"""
        message = 'Tu cuenta ha sido desactivada.'
        if reason:
            message += f' Motivo: {reason}'
        
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='account_deactivated',
            title='Cuenta desactivada',
            message=message,
            priority='critical',
            data={'reason': reason}
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('pages_auth.login_page', _external=True)
                subject, html = EmailTemplates.account_deactivated(
                    user_name=f"{user.first_name} {user.last_name}",
                    reason=reason or "No especificado",
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for account_deactivated: {e}")
        
        return notification
    
    @staticmethod
    def notify_program_changed(user_id: int, from_program: str, to_program: str) -> Notification:
        """Notifica cuando hay un cambio de programa"""
        notification = NotificationService.create_notification(
            user_id=user_id,
            notification_type='program_changed',
            title='Cambio de programa',
            message=f'Has sido cambiado del programa "{from_program}" a "{to_program}".',
            priority='high',
            data={
                'from_program': from_program,
                'to_program': to_program,
                'url': '/user/profile'
            }
        )
        
        # NUEVO: Enviar correo
        try:
            from app.models.user import User
            from app.services.email_service import EmailService
            from app.services.email_templates import EmailTemplates
            user = User.query.get(user_id)
            if user:
                dashboard_url = url_for('program.admission.admission_dashboard', 
                                       slug=user.user_program[0].program.slug if user.user_program else 'general', 
                                       _external=True)
                subject, html = EmailTemplates.program_changed(
                    user_name=f"{user.first_name} {user.last_name}",
                    from_program=from_program,
                    to_program=to_program,
                    dashboard_url=dashboard_url
                )
                EmailService.queue_email(user_id, subject, html, notification.id)
        except Exception as e:
            import logging
            logging.error(f"Error queueing email for program_changed: {e}")
        
        return notification
    
    # ==================== GESTIÓN DE NOTIFICACIONES ====================
    
    @staticmethod
    def mark_as_read(notification_id: int, user_id: int) -> Optional[Notification]:
        """Marca una notificación como leída"""
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=user_id
        ).first()
        
        if notification and not notification.is_read:
            notification.is_read = True
            notification.read_at = now_local()
            db.session.flush()
        
        return notification
    
    @staticmethod
    def mark_all_as_read(user_id: int) -> int:
        """Marca todas las notificaciones de un usuario como leídas"""
        count = Notification.query.filter_by(
            user_id=user_id,
            is_read=False,
            is_deleted=False
        ).update({
            'is_read': True,
            'read_at': now_local()
        })
        db.session.flush()
        return count
    
    @staticmethod
    def delete_notification(notification_id: int, user_id: int) -> Optional[Notification]:
        """Soft delete de una notificación"""
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=user_id
        ).first()
        
        if notification:
            notification.is_deleted = True
            db.session.flush()
        
        return notification
    
    @staticmethod
    def get_user_notifications(
        user_id: int,
        include_read: bool = True,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Notification], int]:
        """Obtiene notificaciones de un usuario con paginación"""
        query = Notification.query.filter_by(
            user_id=user_id,
            is_deleted=False
        )
        
        if not include_read:
            query = query.filter_by(is_read=False)
        
        total = query.count()
        
        notifications = query.order_by(
            Notification.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return notifications, total
    
    @staticmethod
    def get_unread_count(user_id: int) -> int:
        """Obtiene el contador de notificaciones no leídas"""
        return Notification.query.filter_by(
            user_id=user_id,
            is_read=False,
            is_deleted=False
        ).count()
    
    @staticmethod
    def clear_read_notifications(user_id: int) -> int:
        """Elimina todas las notificaciones leídas de un usuario"""
        count = Notification.query.filter_by(
            user_id=user_id,
            is_read=True,
            is_deleted=False
        ).update({'is_deleted': True})
        db.session.flush()
        return count
    
    @staticmethod
    def cleanup_old_notifications(days: int = 30) -> int:
        """Limpia notificaciones antiguas y leídas"""
        cutoff_date = now_local() - timedelta(days=days)
        
        count = Notification.query.filter(
            Notification.created_at < cutoff_date,
            Notification.is_read == True,
            Notification.is_deleted == False
        ).update({'is_deleted': True})
        
        db.session.flush()
        return count
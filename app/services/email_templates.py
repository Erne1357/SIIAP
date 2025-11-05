from flask import render_template
from typing import Dict, Any


class EmailTemplates:
    """Plantillas de correo para diferentes tipos de notificaciones"""
    
    @staticmethod
    def render_email(template_name: str, context: Dict[str, Any]) -> str:
        """Renderiza una plantilla de correo con el contexto dado"""
        return render_template(f'emails/{template_name}.html', **context)
    
    @staticmethod
    def document_approved(user_name: str, archive_name: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para documento aprobado"""
        subject = f"✅ Documento aprobado: {archive_name}"
        html = EmailTemplates.render_email('document_approved', {
            'user_name': user_name,
            'archive_name': archive_name,
            'dashboard_url': dashboard_url
        })
        return subject, html
    
    @staticmethod
    def document_rejected(user_name: str, archive_name: str, reason: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para documento rechazado"""
        subject = f"⚠️ Documento requiere correcciones: {archive_name}"
        html = EmailTemplates.render_email('document_rejected', {
            'user_name': user_name,
            'archive_name': archive_name,
            'reason': reason,
            'dashboard_url': dashboard_url
        })
        return subject, html
    
    @staticmethod
    def coordinator_uploaded(user_name: str, archive_name: str, coordinator_name: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para documento subido por coordinador"""
        subject = f"📄 Documento subido por coordinador: {archive_name}"
        html = EmailTemplates.render_email('coordinator_uploaded', {
            'user_name': user_name,
            'archive_name': archive_name,
            'coordinator_name': coordinator_name,
            'dashboard_url': dashboard_url
        })
        return subject, html
    
    @staticmethod
    def extension_approved(user_name: str, archive_name: str, granted_until: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para prórroga aprobada"""
        subject = f"✅ Prórroga aprobada: {archive_name}"
        html = EmailTemplates.render_email('extension_approved', {
            'user_name': user_name,
            'archive_name': archive_name,
            'granted_until': granted_until,
            'dashboard_url': dashboard_url
        })
        return subject, html
    
    @staticmethod
    def extension_rejected(user_name: str, archive_name: str, reason: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para prórroga rechazada"""
        subject = f"⚠️ Prórroga no aprobada: {archive_name}"
        html = EmailTemplates.render_email('extension_rejected', {
            'user_name': user_name,
            'archive_name': archive_name,
            'reason': reason,
            'dashboard_url': dashboard_url
        })
        return subject, html
    
    @staticmethod
    def appointment_assigned(user_name: str, event_title: str, slot_datetime: str, location: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para cita asignada"""
        subject = f"📅 Cita asignada: {event_title}"
        html = EmailTemplates.render_email('appointment_assigned', {
            'user_name': user_name,
            'event_title': event_title,
            'slot_datetime': slot_datetime,
            'location': location,
            'dashboard_url': dashboard_url
        })
        return subject, html
    
    @staticmethod
    def appointment_cancelled(user_name: str, event_title: str, reason: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para cita cancelada"""
        subject = f"❌ Cita cancelada: {event_title}"
        html = EmailTemplates.render_email('appointment_cancelled', {
            'user_name': user_name,
            'event_title': event_title,
            'reason': reason,
            'dashboard_url': dashboard_url
        })
        return subject, html
    
    @staticmethod
    def event_invitation(user_name: str, event_title: str, event_date: str, description: str, event_url: str) -> tuple[str, str]:
        """Plantilla para invitación a evento"""
        subject = f"🎉 Invitación: {event_title}"
        html = EmailTemplates.render_email('event_invitation', {
            'user_name': user_name,
            'event_title': event_title,
            'event_date': event_date,
            'description': description,
            'event_url': event_url
        })
        return subject, html
    
    @staticmethod
    def password_reset(user_name: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para contraseña reseteada"""
        subject = "🔒 Tu contraseña ha sido reseteada"
        html = EmailTemplates.render_email('password_reset', {
            'user_name': user_name,
            'dashboard_url': dashboard_url
        })
        return subject, html
    
    @staticmethod
    def control_number_assigned(user_name: str, control_number: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para número de control asignado"""
        subject = f"🎓 Número de control asignado: {control_number}"
        html = EmailTemplates.render_email('control_number_assigned', {
            'user_name': user_name,
            'control_number': control_number,
            'dashboard_url': dashboard_url
        })
        return subject, html
    
    @staticmethod
    def program_changed(user_name: str, from_program: str, to_program: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para cambio de programa"""
        subject = f"🔄 Cambio de programa: {to_program}"
        html = EmailTemplates.render_email('program_changed', {
            'user_name': user_name,
            'from_program': from_program,
            'to_program': to_program,
            'dashboard_url': dashboard_url
        })
        return subject, html
    
    @staticmethod
    def account_deactivated(user_name: str, reason: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para cuenta desactivada"""
        subject = "🚫 Tu cuenta ha sido desactivada"
        html = EmailTemplates.render_email('account_deactivated', {
            'user_name': user_name,
            'reason': reason,
            'dashboard_url': dashboard_url
        })
        return subject, html
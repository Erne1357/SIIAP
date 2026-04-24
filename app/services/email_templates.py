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
    def appointment_reassigned(user_name: str, event_title: str, new_slot_datetime: str,
                               old_slot_datetime: str, location: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para cita reasignada por cambio de horario aprobado"""
        subject = f"🔄 Cita reasignada: {event_title}"
        html = EmailTemplates.render_email('appointment_reassigned', {
            'user_name': user_name,
            'event_title': event_title,
            'new_slot_datetime': new_slot_datetime,
            'old_slot_datetime': old_slot_datetime,
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
    def event_reminder(user_name: str, event_title: str, slot_datetime: str,
                       reminder_type: str, location: str, event_url: str) -> tuple[str, str]:
        """Plantilla para recordatorio de evento (24h o 2h antes)."""
        if reminder_type == '24h':
            subject = f"⏰ Recordatorio: {event_title} (mañana)"
            template_name = 'event_reminder_24h'
        else:
            subject = f"⏰ Tu evento comienza pronto: {event_title}"
            template_name = 'event_reminder_2h'

        html = EmailTemplates.render_email(template_name, {
            'user_name': user_name,
            'event_title': event_title,
            'slot_datetime': slot_datetime,
            'location': location,
            'event_url': event_url,
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

    @staticmethod
    def deliberation_accepted(user_name: str, program_name: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para aceptación en deliberación"""
        subject = f"🎓 ¡Felicidades! Has sido aceptado en {program_name}"
        html = EmailTemplates.render_email('deliberation_accepted', {
            'user_name': user_name,
            'program_name': program_name,
            'dashboard_url': dashboard_url
        })
        return subject, html

    @staticmethod
    def deliberation_rejected(user_name: str, program_name: str, rejection_type: str,
                               notes: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para rechazo o solicitud de correcciones en deliberación"""
        if rejection_type == 'partial':
            subject = f"⚠️ Se requieren correcciones en tu expediente — {program_name}"
        else:
            subject = f"📋 Resultado del proceso de admisión — {program_name}"
        html = EmailTemplates.render_email('deliberation_rejected', {
            'user_name': user_name,
            'program_name': program_name,
            'rejection_type': rejection_type,
            'notes': notes,
            'dashboard_url': dashboard_url
        })
        return subject, html

    @staticmethod
    def acceptance_docs_ready(user_name: str, program_name: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para documentos de aceptación disponibles"""
        subject = f"📄 Tus documentos de aceptación están listos — {program_name}"
        html = EmailTemplates.render_email('acceptance_docs_ready', {
            'user_name': user_name,
            'program_name': program_name,
            'dashboard_url': dashboard_url
        })
        return subject, html

    # ==================== PERMANENCIA ====================

    @staticmethod
    def permanence_doc_rejected(user_name: str, document_label: str, reason: str,
                                 dashboard_url: str) -> tuple[str, str]:
        """Plantilla para documento de permanencia rechazado"""
        subject = f"⚠️ Documento rechazado: {document_label}"
        html = EmailTemplates.render_email('permanence_doc_rejected', {
            'user_name': user_name,
            'document_label': document_label,
            'reason': reason,
            'dashboard_url': dashboard_url,
        })
        return subject, html

    @staticmethod
    def enrollment_receipt_rejected(user_name: str, program_name: str, reason: str,
                                     dashboard_url: str) -> tuple[str, str]:
        """Plantilla para carta de número de control rechazada"""
        subject = f"⚠️ Carta rechazada — {program_name}"
        html = EmailTemplates.render_email('enrollment_receipt_rejected', {
            'user_name': user_name,
            'program_name': program_name,
            'reason': reason,
            'dashboard_url': dashboard_url,
        })
        return subject, html

    @staticmethod
    def enrollment_receipt_approved(user_name: str, program_name: str,
                                     dashboard_url: str) -> tuple[str, str]:
        """Plantilla para carta de número de control aprobada"""
        subject = f"✅ Carta aprobada — {program_name}"
        html = EmailTemplates.render_email('enrollment_receipt_approved', {
            'user_name': user_name,
            'program_name': program_name,
            'dashboard_url': dashboard_url,
        })
        return subject, html

    @staticmethod
    def deadline_created(user_name: str, deadline_label: str, closes_at: str,
                          dashboard_url: str) -> tuple[str, str]:
        """Plantilla para nueva ventana de entrega"""
        subject = f"📄 Nueva ventana de entrega: {deadline_label}"
        html = EmailTemplates.render_email('deadline_created', {
            'user_name': user_name,
            'deadline_label': deadline_label,
            'closes_at': closes_at,
            'dashboard_url': dashboard_url,
        })
        return subject, html

    @staticmethod
    def enrollment_status_changed(user_name: str, program_name: str, period_name: str,
                                   semester_number: int, status: str, status_label: str,
                                   dashboard_url: str) -> tuple[str, str]:
        """Plantilla para cambio de estado de inscripción"""
        emoji = '🚫' if status == 'dropped' else '⏸️'
        subject = f"{emoji} {status_label} — {program_name}"
        html = EmailTemplates.render_email('enrollment_status_changed', {
            'user_name': user_name,
            'program_name': program_name,
            'period_name': period_name,
            'semester_number': semester_number,
            'status': status,
            'status_label': status_label,
            'dashboard_url': dashboard_url,
        })
        return subject, html

    @staticmethod
    def leave_request_result(user_name: str, program_name: str, approved: bool,
                              reason: str, dashboard_url: str) -> tuple[str, str]:
        """Plantilla para resultado de solicitud de baja temporal"""
        status_text = 'aprobada' if approved else 'rechazada'
        emoji = '✅' if approved else '❌'
        subject = f"{emoji} Solicitud de baja temporal {status_text} — {program_name}"
        html = EmailTemplates.render_email('leave_request_result', {
            'user_name': user_name,
            'program_name': program_name,
            'approved': approved,
            'reason': reason,
            'dashboard_url': dashboard_url,
        })
        return subject, html
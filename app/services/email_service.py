from app import db
from app.models.email_queue import EmailQueue
from app.models.user import User
from app.utils.ms_graph import graph_send_mail, acquire_token_silent, is_connected
from app.utils.datetime_utils import now_local
from datetime import timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Servicio para gestión y envío de correos con cola"""
    
    @staticmethod
    def queue_email(user_id: int, subject: str, html_content: str, 
                   notification_id: Optional[int] = None) -> EmailQueue:
        """
        Agrega un correo a la cola.
        Si hay sesión activa de Microsoft, intenta enviarlo inmediatamente.
        """
        user = User.query.get(user_id)
        if not user or not user.email:
            raise ValueError(f"Usuario {user_id} no tiene email configurado")
        
        email_item = EmailQueue(
            user_id=user_id,
            notification_id=notification_id,
            recipient_email=user.email,
            subject=subject,
            html_content=html_content,
            status='pending',
            attempts=0
        )
        
        db.session.add(email_item)
        db.session.flush()
        
        # Intentar enviar inmediatamente si hay conexión
        if is_connected():
            EmailService._try_send_email(email_item)
        
        return email_item
    
    @staticmethod
    def _try_send_email(email_item: EmailQueue) -> bool:
        """
        Intenta enviar un email de la cola.
        Retorna True si se envió exitosamente.
        """
        try:
            token = acquire_token_silent()
            if not token:
                logger.warning(f"No hay token para enviar email {email_item.id}")
                return False
            
            response = graph_send_mail(
                access_token=token,
                subject=email_item.subject,
                content_html=email_item.html_content,
                to_list=[email_item.recipient_email],
                save_to_sent=True
            )
            
            if response.status_code in (200, 202):
                email_item.status = 'sent'
                email_item.sent_at = now_local()
                email_item.error_message = None
                db.session.flush()
                logger.info(f"Email {email_item.id} enviado exitosamente")
                return True
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"Error enviando email {email_item.id}: {str(e)}")
            email_item.attempts += 1
            email_item.error_message = str(e)
            
            if email_item.attempts >= email_item.max_attempts:
                email_item.status = 'failed'
            else:
                # Reintentar en 5 minutos
                email_item.next_retry_at = now_local() + timedelta(minutes=5)
            
            db.session.flush()
            return False
    
    @staticmethod
    def process_queue(limit: int = 50) -> dict:
        """
        Procesa la cola de correos pendientes.
        Retorna estadísticas del procesamiento.
        """
        if not is_connected():
            return {
                'processed': 0,
                'sent': 0,
                'failed': 0,
                'error': 'No hay sesión activa de Microsoft'
            }
        
        # Obtener correos pendientes
        pending = EmailQueue.query.filter_by(status='pending').order_by(
            EmailQueue.created_at.asc()
        ).limit(limit).all()
        
        sent_count = 0
        failed_count = 0
        
        for email_item in pending:
            if EmailService._try_send_email(email_item):
                sent_count += 1
            else:
                failed_count += 1
        
        db.session.commit()
        
        return {
            'processed': len(pending),
            'sent': sent_count,
            'failed': failed_count
        }
    
    @staticmethod
    def retry_failed(limit: int = 20) -> dict:
        """Reintenta enviar correos fallidos que no han superado max_attempts"""
        if not is_connected():
            return {
                'processed': 0,
                'sent': 0,
                'error': 'No hay sesión activa de Microsoft'
            }
        
        failed = EmailQueue.query.filter(
            EmailQueue.status == 'pending',
            EmailQueue.attempts > 0,
            EmailQueue.attempts < EmailQueue.max_attempts
        ).limit(limit).all()
        
        sent_count = 0
        for email_item in failed:
            if EmailService._try_send_email(email_item):
                sent_count += 1
        
        db.session.commit()
        
        return {
            'processed': len(failed),
            'sent': sent_count
        }
    
    @staticmethod
    def get_queue_stats() -> dict:
        """Obtiene estadísticas de la cola"""
        pending = EmailQueue.query.filter_by(status='pending').count()
        sent = EmailQueue.query.filter_by(status='sent').count()
        failed = EmailQueue.query.filter_by(status='failed').count()
        
        return {
            'pending': pending,
            'sent': sent,
            'failed': failed,
            'total': pending + sent + failed,
            'connected': is_connected()
        }
    
    @staticmethod
    def get_pending_emails(limit: int = 50, offset: int = 0):
        """Obtiene correos pendientes con paginación"""
        query = EmailQueue.query.filter_by(status='pending').order_by(
            EmailQueue.created_at.desc()
        )
        total = query.count()
        items = query.limit(limit).offset(offset).all()
        
        return {
            'items': [item.to_dict() for item in items],
            'total': total
        }
    
    @staticmethod
    def clear_old_sent_emails(days: int = 30) -> int:
        """Elimina correos enviados hace más de X días"""
        cutoff = now_local() - timedelta(days=days)
        count = EmailQueue.query.filter(
            EmailQueue.status == 'sent',
            EmailQueue.sent_at < cutoff
        ).delete()
        db.session.commit()
        return count
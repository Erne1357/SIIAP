from app import db
from app.models.email_queue import EmailQueue
from app.models.user import User
from app.utils.ms_graph import graph_send_mail, acquire_token_silent, is_connected
from app.utils.datetime_utils import now_local
from sqlalchemy import and_, or_, update
from sqlalchemy.orm import defer
from datetime import timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Value written over `html_content` once a mail is no longer sendable. The
# column is NOT NULL, so the body is blanked rather than nulled.
PURGED_BODY = ''

# How long a rendered body survives after the mail stopped being sendable.
# See EmailService.purge_delivered_bodies for the reasoning behind 24 h.
BODY_RETENTION_HOURS = 24

# A worker claims a row by moving it to 'sending' and stamping
# `next_retry_at` with the end of its lease. If the worker dies mid-send the
# row would stay 'sending' forever, so once the lease is over any worker may
# claim it again. Graph answers in seconds; 15 minutes is far beyond a send.
SENDING_LEASE = timedelta(minutes=15)

# Rows not yet delivered: queued, or currently held by a worker.
UNDELIVERED_STATUSES = ('pending', 'sending')


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

        # Delegar el envío a Celery para evitar bloqueos síncronos en la UI
        # Usamos countdown=1 para dar tiempo a que la transacción principal haga commit
        try:
            from app.tasks.notifications import send_email_async
            send_email_async.apply_async(args=[email_item.id], countdown=1)
        except Exception as err:
            logger.warning(f"No se pudo encolar la tarea de email async: {err}")

        # Notificar en tiempo real al panel de administración
        EmailService._emit_queue_update()

        return email_item

    @staticmethod
    def _emit_queue_update():
        """Emite el estado actual de la cola al panel de admin vía WebSocket."""
        try:
            from app.extensions import socketio
            pending = EmailQueue.query.filter(
                EmailQueue.status.in_(UNDELIVERED_STATUSES)
            ).count()
            failed = EmailQueue.query.filter_by(status='failed').count()
            socketio.emit(
                'email:queue_update',
                {'pending': pending, 'failed': failed},
                room='role:postgraduate_admin',
            )
        except Exception:
            pass
    
    @staticmethod
    def _claimable(now):
        """
        SQL condition for a row a worker may take: 'pending', or 'sending'
        whose lease (`next_retry_at`) is over because its worker died.
        """
        return or_(
            EmailQueue.status == 'pending',
            and_(
                EmailQueue.status == 'sending',
                or_(EmailQueue.next_retry_at.is_(None), EmailQueue.next_retry_at < now),
            ),
        )

    @staticmethod
    def _claim(email_item: EmailQueue) -> bool:
        """
        Atomically takes ownership of a row before sending it.

        A single conditional UPDATE is atomic on both SQLite and PostgreSQL:
        when two workers race for the same row only one sees rowcount == 1,
        the other gets 0 and must not send. The claim is committed right away
        so it is visible to every other worker for the whole send (and no row
        lock is held across the network call).
        """
        now = now_local()
        result = db.session.execute(
            update(EmailQueue)
            .where(EmailQueue.id == email_item.id, EmailService._claimable(now))
            .values(status='sending', next_retry_at=now + SENDING_LEASE)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            return False
        db.session.commit()
        # Re-read the row: the claim must still be ours before mailing anyone.
        db.session.refresh(email_item)
        return email_item.status == 'sending'

    @staticmethod
    def _try_send_email(email_item: EmailQueue) -> bool:
        """
        Intenta enviar un email de la cola.
        Retorna True si se envió exitosamente.

        Returns False without touching the row when another worker already
        holds it (see _claim).
        """
        if not EmailService._claim(email_item):
            logger.info(f"Email {email_item.id} ya está siendo enviado por otro proceso; se omite")
            return False
        return EmailService._deliver_claimed(email_item)

    @staticmethod
    def _deliver_claimed(email_item: EmailQueue) -> bool:
        """
        Sends a row this worker has already claimed. Every path leaves the row
        out of 'sending': 'sent', back to 'pending' for a retry, or 'failed'.
        """
        # A blanked body means the retention purge already reclaimed this row,
        # which only happens once the mail is no longer sendable ('sent', or
        # 'failed' past max_attempts). Sending it would deliver an empty
        # message; fail it loudly instead of silently mailing nothing.
        if not email_item.html_content:
            logger.error(
                f"Email {email_item.id} sin cuerpo (purgado por retención); no se envía"
            )
            email_item.status = 'failed'
            email_item.error_message = (
                'El cuerpo del correo fue purgado por la política de retención; '
                'no se puede reenviar.'
            )
            db.session.flush()
            return False

        try:
            token = acquire_token_silent()
            if not token:
                logger.warning(f"No hay token para enviar email {email_item.id}")
                # Not an attempt: release the claim so the next sweep takes it.
                email_item.status = 'pending'
                email_item.next_retry_at = None
                db.session.flush()
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
                email_item.next_retry_at = None
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
                email_item.status = 'pending'
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
        
        # Obtener correos pendientes (y los 'sending' cuyo worker murió)
        pending = EmailQueue.query.filter(
            EmailService._claimable(now_local())
        ).order_by(
            EmailQueue.created_at.asc()
        ).limit(limit).all()

        processed = 0
        sent_count = 0
        failed_count = 0

        for email_item in pending:
            # Another worker may have claimed it since the SELECT: skip it,
            # it is neither processed nor failed here.
            if not EmailService._claim(email_item):
                continue
            processed += 1
            if EmailService._deliver_claimed(email_item):
                sent_count += 1
            else:
                failed_count += 1

        db.session.commit()

        return {
            'processed': processed,
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
            EmailService._claimable(now_local()),
            EmailQueue.attempts > 0,
            EmailQueue.attempts < EmailQueue.max_attempts
        ).limit(limit).all()

        processed = 0
        sent_count = 0
        for email_item in failed:
            if not EmailService._claim(email_item):
                continue
            processed += 1
            if EmailService._deliver_claimed(email_item):
                sent_count += 1

        db.session.commit()

        return {
            'processed': processed,
            'sent': sent_count
        }

    @staticmethod
    def get_queue_stats() -> dict:
        """Obtiene estadísticas de la cola"""
        # 'sending' rows are still undelivered: they count as pending.
        pending = EmailQueue.query.filter(EmailQueue.status.in_(UNDELIVERED_STATUSES)).count()
        sent = EmailQueue.query.filter_by(status='sent').count()
        failed = EmailQueue.query.filter_by(status='failed').count()
        
        return {
            'pending': pending,
            'sent': sent,
            'failed': failed,
            'total': pending + sent + failed,
        }
    
    @staticmethod
    def get_pending_emails(limit: int = 50, offset: int = 0):
        """
        Obtiene correos pendientes con paginación (sin el cuerpo del correo).

        `defer` keeps `html_content` out of the SELECT: the rendered body — which
        for password-reset and activation mail is a live one-time token link —
        never reaches the application layer on a listing, let alone the client.
        """
        query = EmailQueue.query.filter(
            EmailQueue.status.in_(UNDELIVERED_STATUSES)
        ).order_by(
            EmailQueue.created_at.desc()
        )
        total = query.count()
        items = (
            query.options(defer(EmailQueue.html_content))
            .limit(limit)
            .offset(offset)
            .all()
        )

        return {
            'items': [item.to_dict() for item in items],
            'total': total
        }

    @staticmethod
    def purge_delivered_bodies(hours: int = BODY_RETENTION_HOURS) -> dict:
        """
        Blanks `html_content` on mail that can no longer be sent.

        Rationale for the window (24 h by default): once a mail is 'sent' the
        rendered body has no operational use — the sender already consumed it
        and no code path re-reads it (senders only claim 'pending'/'sending' rows).
        What it does keep is a copy of whatever the template rendered, including
        password-reset and staff-activation token links, which stay valid for up
        to 7 days (`generate_token` default `ttl_days=7`). Keeping the body for
        24 h leaves one working day to diagnose "what did we actually send?"
        while ensuring a live credential stops existing in a second place long
        before it expires. 'failed' rows are purged on the same clock measured
        from `created_at`: nothing can ever resend them.

        The rows themselves are kept — subject, recipient, status, attempts and
        timestamps are the delivery audit trail and carry no secret.
        """
        cutoff = now_local() - timedelta(hours=hours)

        sent = EmailQueue.query.filter(
            EmailQueue.status == 'sent',
            EmailQueue.sent_at.isnot(None),
            EmailQueue.sent_at < cutoff,
            EmailQueue.html_content != PURGED_BODY,
        ).update({'html_content': PURGED_BODY}, synchronize_session=False)

        failed = EmailQueue.query.filter(
            EmailQueue.status == 'failed',
            EmailQueue.created_at < cutoff,
            EmailQueue.html_content != PURGED_BODY,
        ).update({'html_content': PURGED_BODY}, synchronize_session=False)

        db.session.commit()

        return {
            'sent_purged': sent,
            'failed_purged': failed,
            'total': sent + failed,
            'hours': hours,
        }
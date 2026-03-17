"""
Tareas de mantenimiento periódico del sistema SIIAP.

Programadas automáticamente a través de Celery Beat (ver app/celery_app.py):
  - cleanup_expired_admission_files  → diario a las 02:00
  - apply_retention_policies         → lunes a las 03:00
  - cleanup_old_notifications        → diario a las 04:00
"""

import logging
import os
from datetime import datetime, timedelta

from app.celery_app import celery

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. LIMPIEZA DE ARCHIVOS DE ADMISIÓN EXPIRADOS
# ─────────────────────────────────────────────────────────────────────────────

@celery.task(
    name='app.tasks.maintenance.cleanup_expired_admission_files',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def cleanup_expired_admission_files(self):
    """
    Elimina archivos físicos y submissions de procesos de admisión expirados.

    Un proceso se considera expirado cuando:
      - El aspirante lleva más de 2 períodos académicos activos sin completar
        la admisión (estado != 'completed').
      - O cuando la fecha actual supera la fecha límite configurada en el
        UserProgram/AcademicPeriod.

    Los archivos físicos se eliminan del disco; las submissions quedan con
    estado 'expired' en la base de datos (no se borran los registros para
    mantener auditoría).
    """
    from app import db
    from app.models.submission import Submission
    from app.models.user_program import UserProgram
    from app.config import Config

    logger.info("[cleanup_expired_admission_files] Iniciando limpieza de archivos expirados...")

    try:
        # Obtiene procesos de admisión en estado 'in_progress' cuya fecha límite
        # ya pasó. Ajusta esta query según el modelo real de tu proyecto.
        expired_programs = UserProgram.query.filter(
            UserProgram.status == 'in_progress',
            UserProgram.deadline < datetime.utcnow(),
        ).all()

        deleted_files = 0
        marked_expired = 0

        for up in expired_programs:
            # Marca el proceso como expirado
            up.status = 'expired'
            marked_expired += 1

            # Obtiene todos los documentos subidos en este proceso
            submissions = Submission.query.filter_by(user_program_id=up.id).all()

            for sub in submissions:
                # Elimina el archivo físico si existe
                if sub.file_path:
                    full_path = os.path.join(str(Config.UPLOAD_FOLDER), sub.file_path)
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                            deleted_files += 1
                        except OSError as e:
                            logger.warning(
                                f"No se pudo eliminar {full_path}: {e}"
                            )

                sub.status = 'expired'

        db.session.commit()

        logger.info(
            f"[cleanup_expired_admission_files] Completado. "
            f"Procesos expirados: {marked_expired}, archivos eliminados: {deleted_files}"
        )
        return {'expired_programs': marked_expired, 'deleted_files': deleted_files}

    except Exception as exc:
        db.session.rollback()
        logger.error(f"[cleanup_expired_admission_files] Error: {exc}", exc_info=True)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# 2. APLICAR POLÍTICAS DE RETENCIÓN
# ─────────────────────────────────────────────────────────────────────────────

@celery.task(
    name='app.tasks.maintenance.apply_retention_policies',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def apply_retention_policies(self):
    """
    Aplica las RetentionPolicy definidas en la base de datos.

    Para cada política:
      - Si keep_forever=True → no hace nada.
      - Si keep_years está definido → elimina archivos de usuarios cuyo evento
        (graduación, baja, inscripción) ocurrió hace más de keep_years años.
    """
    from app import db
    from app.models.retention_policy import RetentionPolicy
    from app.models.submission import Submission
    from app.models.user_program import UserProgram
    from app.config import Config

    logger.info("[apply_retention_policies] Iniciando aplicación de políticas de retención...")

    try:
        policies = RetentionPolicy.query.filter_by(keep_forever=False).all()
        deleted_files = 0

        for policy in policies:
            if not policy.keep_years:
                continue

            cutoff_date = datetime.utcnow() - timedelta(days=policy.keep_years * 365)

            # Encuentra UserPrograms con el evento de apply_after anterior al cutoff
            # Ajusta el campo de fecha según tu modelo real.
            expired_ups = UserProgram.query.filter(
                UserProgram.archive_id == policy.archive_id,
                UserProgram.status == policy.apply_after,
                UserProgram.updated_at < cutoff_date,
            ).all()

            for up in expired_ups:
                subs = Submission.query.filter_by(
                    user_program_id=up.id,
                    archive_id=policy.archive_id,
                ).all()

                for sub in subs:
                    if sub.file_path:
                        full_path = os.path.join(str(Config.UPLOAD_FOLDER), sub.file_path)
                        if os.path.exists(full_path):
                            try:
                                os.remove(full_path)
                                deleted_files += 1
                            except OSError as e:
                                logger.warning(f"No se pudo eliminar {full_path}: {e}")

                    sub.file_path = None
                    sub.status = 'purged'

        db.session.commit()

        logger.info(
            f"[apply_retention_policies] Completado. Archivos purgados: {deleted_files}"
        )
        return {'deleted_files': deleted_files}

    except Exception as exc:
        db.session.rollback()
        logger.error(f"[apply_retention_policies] Error: {exc}", exc_info=True)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# 3. LIMPIEZA DE NOTIFICACIONES ANTIGUAS
# ─────────────────────────────────────────────────────────────────────────────

@celery.task(
    name='app.tasks.maintenance.cleanup_old_notifications',
    bind=True,
)
def cleanup_old_notifications(self, days: int = 30):
    """
    Marca como eliminadas (soft delete) las notificaciones leídas con más de
    `days` días de antigüedad.
    """
    from app import db
    from app.services.notification_service import NotificationService

    logger.info(f"[cleanup_old_notifications] Limpiando notificaciones con más de {days} días...")

    try:
        count = NotificationService.cleanup_old_notifications(days=days)
        db.session.commit()
        logger.info(f"[cleanup_old_notifications] Notificaciones marcadas: {count}")
        return {'marked_deleted': count}

    except Exception as exc:
        db.session.rollback()
        logger.error(f"[cleanup_old_notifications] Error: {exc}", exc_info=True)
        raise self.retry(exc=exc)

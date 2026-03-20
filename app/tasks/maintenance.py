"""
Tareas de mantenimiento periódico del sistema SIIAP.

Programadas automáticamente a través de Celery Beat (ver app/celery_app.py):
  - cleanup_expired_admission_files    → diario a las 02:00
  - apply_retention_policies           → lunes a las 03:00
  - cleanup_old_notifications          → diario a las 04:00
  - check_deferral_expirations         → diario a las 08:00
  - notify_pending_permanence_docs     → lunes a las 09:00
"""

import logging
import os
from datetime import datetime, timedelta

from app.celery_app import celery

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. LIMPIEZA DE ARCHIVOS DE ADMISIÓN EXPIRADOS
# ─────────────────────────────────────────────────────────────────────────────

def _periods_elapsed_since(enrollment_period_code: str) -> int:
    """
    Cuenta cuántos periodos han cerrado su proceso de admisión después del periodo
    de inscripción (código YYYYN comparado lexicográficamente, lo que equivale a
    orden cronológico por el formato fijo de 5 caracteres).
    """
    from app.models.academic_period import AcademicPeriod
    return (
        AcademicPeriod.query
        .filter(
            AcademicPeriod.code > enrollment_period_code,
            AcademicPeriod.admission_end_date < datetime.utcnow(),
        )
        .count()
    )


@celery.task(
    name='app.tasks.maintenance.cleanup_expired_admission_files',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def cleanup_expired_admission_files(self):
    """
    Expira procesos de admisión incompletos que superaron el límite de 2 periodos.

    Un proceso se considera expirado cuando han cerrado 2 o más periodos de
    admisión DESPUÉS del periodo en que el aspirante se inscribió
    (UserProgram.admission_period_id). Esto le da al aspirante el periodo de
    inscripción más un periodo adicional para completar el proceso.

    Procesos sin admission_period_id (registros anteriores al Bloque 1) se omiten
    para no afectar datos históricos.

    Los archivos físicos se eliminan del disco; las submissions quedan con estado
    'expired' en la base de datos para mantener auditoría.
    """
    from app import db
    from app.models.submission import Submission
    from app.models.program_step import ProgramStep
    from app.models.user_program import UserProgram
    from app.models.academic_period import AcademicPeriod
    from app.config import Config

    logger.info("[cleanup_expired_admission_files] Iniciando limpieza de archivos expirados...")

    try:
        from app.services.user_history_service import UserHistoryService

        # Candidatos: procesos incompletos con periodo de inscripción conocido
        candidates = (
            UserProgram.query
            .join(AcademicPeriod, UserProgram.admission_period_id == AcademicPeriod.id)
            .filter(
                UserProgram.admission_status.in_(['in_progress', 'interview_completed', 'deliberation']),
                UserProgram.admission_period_id.isnot(None),
            )
            .all()
        )

        deleted_files = 0
        marked_expired = 0

        for up in candidates:
            enrollment_period = AcademicPeriod.query.get(up.admission_period_id)
            if not enrollment_period:
                continue

            elapsed = _periods_elapsed_since(enrollment_period.code)
            if elapsed < 2:
                continue  # todavía dentro del plazo permitido

            up.admission_status = 'expired'
            marked_expired += 1

            # Eliminar archivos físicos de las submissions de este proceso
            submissions = (
                Submission.query
                .join(ProgramStep, Submission.program_step_id == ProgramStep.id)
                .filter(
                    Submission.user_id == up.user_id,
                    ProgramStep.program_id == up.program_id,
                )
                .all()
            )

            files_deleted_this_user = 0
            for sub in submissions:
                if sub.file_path:
                    full_path = os.path.join(str(Config.UPLOAD_FOLDER), sub.file_path)
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                            deleted_files += 1
                            files_deleted_this_user += 1
                        except OSError as e:
                            logger.warning(f"No se pudo eliminar {full_path}: {e}")

                sub.status = 'expired'

            UserHistoryService.log_action(
                user_id=up.user_id,
                admin_id=None,
                action='data_cleanup',
                details=(
                    f"Proceso de admisión expirado automáticamente tras {elapsed} periodos "
                    f"sin completar. Archivos eliminados: {files_deleted_this_user}. "
                    f"Programa: {up.program.name}. Período de inscripción: {enrollment_period.name}."
                ),
            )

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

            # Encuentra UserPrograms con admission_status igual a apply_after
            # (ej: 'rejected', 'enrolled') cuyo updated_at sea anterior al cutoff.
            # Nota: UserProgram no tiene archive_id directamente; se filtra por
            # submissions que pertenezcan al archive de la política.
            expired_ups = UserProgram.query.filter(
                UserProgram.admission_status == policy.apply_after,
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


# ─────────────────────────────────────────────────────────────────────────────
# 4. EXPIRACIÓN DE DIFERIMIENTOS Y NOTIFICACIONES DE VENCIMIENTO PRÓXIMO
# ─────────────────────────────────────────────────────────────────────────────

@celery.task(
    name='app.tasks.maintenance.check_deferral_expirations',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def check_deferral_expirations(self):
    """
    Revisa diferimientos activos:
    - Marca como 'expired' los cuyo periodo diferido ya terminó.
    - Envía notificación 30 días antes del vencimiento (una sola vez).
    - Si el aspirante agotó sus diferimientos y el periodo expiró,
      cambia admission_status a 'expired'.

    Programada diariamente a las 08:00.
    """
    from app.services.deferral_service import check_and_expire_deferrals

    logger.info("[check_deferral_expirations] Revisando diferimientos...")

    try:
        result = check_and_expire_deferrals()
        logger.info(
            f"[check_deferral_expirations] Completado. "
            f"Expirados: {result['expired']}, notificaciones enviadas: {result['notified']}"
        )
        return result

    except Exception as exc:
        logger.error(f"[check_deferral_expirations] Error: {exc}", exc_info=True)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# 5. NOTIFICAR ESTUDIANTES CON INSCRIPCIÓN SEMESTRAL PENDIENTE
# ─────────────────────────────────────────────────────────────────────────────

@celery.task(
    name='app.tasks.maintenance.notify_pending_permanence_docs',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def notify_pending_permanence_docs(self):
    """
    Notifica a estudiantes activos cuya inscripción semestral aún no ha sido
    confirmada por el coordinador para el período académico activo.

    Sólo notifica si existe un período activo. No re-notifica a estudiantes
    que ya tienen su inscripción confirmada (enrollment_confirmed=True).

    Programada semanalmente los lunes a las 09:00.
    """
    from app import db
    from app.models.user_program import UserProgram
    from app.models.semester_enrollment import SemesterEnrollment
    from app.models.academic_period import AcademicPeriod
    from app.services.notification_service import NotificationService

    logger.info("[notify_pending_permanence_docs] Iniciando notificaciones de permanencia pendiente...")

    try:
        active_period = AcademicPeriod.get_active_period()
        if not active_period:
            logger.info("[notify_pending_permanence_docs] Sin período activo. No se envían notificaciones.")
            return {'notified': 0, 'reason': 'no_active_period'}

        enrolled_ups = UserProgram.query.filter_by(admission_status='enrolled').all()

        notified = 0
        for up in enrolled_ups:
            enrollment = SemesterEnrollment.query.filter_by(
                user_program_id=up.id,
                academic_period_id=active_period.id,
            ).first()

            if enrollment and enrollment.enrollment_confirmed:
                continue  # ya confirmado, no notificar

            NotificationService.create_notification(
                user_id=up.user_id,
                notification_type='permanence_pending',
                title='Inscripción semestral pendiente de confirmación',
                message=(
                    f'Tu inscripción para el período {active_period.name} '
                    f'aún no ha sido confirmada por la coordinación de tu programa. '
                    f'Comunícate con tu coordinador para más información.'
                ),
                priority='medium',
                action_url='/dashboard',
            )
            notified += 1

        db.session.commit()
        logger.info(f"[notify_pending_permanence_docs] Notificaciones enviadas: {notified}")
        return {'notified': notified, 'period': active_period.name}

    except Exception as exc:
        db.session.rollback()
        logger.error(f"[notify_pending_permanence_docs] Error: {exc}", exc_info=True)
        raise self.retry(exc=exc)

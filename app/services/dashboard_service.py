# app/services/dashboard_service.py

from sqlalchemy import func, and_, or_
from app import db
from app.models import User, Program, Submission, UserProgram, Event, EventSlot, ProgramStep, Step, Phase
from datetime import datetime, timedelta
from app.utils.datetime_utils import now_local


class DashboardService:
    """Servicio para obtener métricas y datos de los dashboards"""

    @staticmethod
    def get_program_admin_metrics(program_id):
        """
        Obtiene métricas para el dashboard del coordinador/admin de programa

        Args:
            program_id: ID del programa del cual obtener métricas

        Returns:
            dict con métricas de admisión
        """
        # Total de solicitantes (applicants con status pending o active en este programa)
        total_applicants = db.session.query(func.count(UserProgram.user_id)).filter(
            UserProgram.program_id == program_id,
            UserProgram.status.in_(['pending', 'active'])
        ).scalar() or 0

        # Documentos pendientes de revisión (submissions con status 'review')
        pending_reviews = db.session.query(func.count(Submission.id)).join(
            ProgramStep, Submission.program_step_id == ProgramStep.id
        ).filter(
            ProgramStep.program_id == program_id,
            Submission.status == 'review'
        ).scalar() or 0

        # Solicitudes aprobadas (todos los documentos en 'approved')
        # Obtener usuarios con todas sus submissions aprobadas
        approved_count = 0
        rejected_count = 0

        applicants = db.session.query(UserProgram).filter(
            UserProgram.program_id == program_id,
            UserProgram.status == 'pending'
        ).all()

        for applicant in applicants:
            # Obtener submissions del usuario para este programa
            submissions = db.session.query(Submission).join(
                ProgramStep, Submission.program_step_id == ProgramStep.id
            ).filter(
                Submission.user_id == applicant.user_id,
                ProgramStep.program_id == program_id
            ).all()

            if submissions:
                # Verificar si todos están aprobados
                all_approved = all(s.status == 'approved' for s in submissions)
                has_rejected = any(s.status == 'rejected' for s in submissions)

                if all_approved:
                    approved_count += 1
                elif has_rejected:
                    rejected_count += 1

        # Entrevistas programadas (EventSlots con status 'booked' para este programa)
        from app.models.event import EventWindow
        interviews_scheduled = db.session.query(func.count(EventSlot.id)).join(
            EventWindow, EventSlot.event_window_id == EventWindow.id
        ).join(
            Event, EventWindow.event_id == Event.id
        ).filter(
            Event.program_id == program_id,
            Event.type == 'interview',
            EventSlot.status == 'booked'
        ).scalar() or 0

        # Solicitudes rechazadas
        # Ya calculado arriba

        # Documentos totales subidos
        total_submissions = db.session.query(func.count(Submission.id)).join(
            ProgramStep, Submission.program_step_id == ProgramStep.id
        ).filter(
            ProgramStep.program_id == program_id
        ).scalar() or 0

        return {
            'total_applicants': total_applicants,
            'pending_reviews': pending_reviews,
            'approved_applications': approved_count,
            'rejected_applications': rejected_count,
            'interviews_scheduled': interviews_scheduled,
            'total_submissions': total_submissions,
            'in_process': total_applicants - approved_count - rejected_count
        }

    @staticmethod
    def get_postgraduate_admin_metrics():
        """
        Obtiene métricas globales para el dashboard del administrador de posgrado

        Returns:
            dict con métricas globales de todos los programas
        """
        # Total de programas activos
        total_programs = db.session.query(func.count(Program.id)).scalar() or 0

        # Total de solicitantes en todos los programas
        total_applicants = db.session.query(func.count(UserProgram.id)).filter(
            UserProgram.status.in_(['pending', 'active'])
        ).scalar() or 0

        # Total de estudiantes activos
        total_students = db.session.query(func.count(UserProgram.id)).filter(
            UserProgram.status == 'active'
        ).scalar() or 0

        # Documentos pendientes de revisión globalmente
        pending_reviews = db.session.query(func.count(Submission.id)).filter(
            Submission.status == 'review'
        ).scalar() or 0

        # Entrevistas pendientes de programar
        # (usuarios con documentos aprobados pero sin entrevista)
        interviews_pending = 0  # Simplificado por ahora

        # Métricas por programa
        programs = db.session.query(Program).all()
        programs_stats = []

        for program in programs:
            applicants_count = db.session.query(func.count(UserProgram.user_id)).filter(
                UserProgram.program_id == program.id,
                UserProgram.status.in_(['pending', 'active'])
            ).scalar() or 0

            pending_docs = db.session.query(func.count(Submission.id)).join(
                ProgramStep, Submission.program_step_id == ProgramStep.id
            ).filter(
                ProgramStep.program_id == program.id,
                Submission.status == 'review'
            ).scalar() or 0

            programs_stats.append({
                'id': program.id,
                'name': program.name,
                'slug': program.slug,
                'applicants': applicants_count,
                'pending_docs': pending_docs
            })

        return {
            'total_programs': total_programs,
            'total_applicants': total_applicants,
            'total_students': total_students,
            'pending_reviews': pending_reviews,
            'interviews_pending': interviews_pending,
            'programs_stats': programs_stats
        }

    @staticmethod
    def get_recent_submissions(program_id, limit=5):
        """
        Obtiene las últimas submissions para un programa

        Args:
            program_id: ID del programa
            limit: Número máximo de submissions a retornar

        Returns:
            list de submissions recientes
        """
        submissions = db.session.query(Submission).join(
            ProgramStep, Submission.program_step_id == ProgramStep.id
        ).join(
            User, Submission.user_id == User.id
        ).filter(
            ProgramStep.program_id == program_id,
            Submission.status.in_(['review', 'pending'])
        ).order_by(
            Submission.upload_date.desc()
        ).limit(limit).all()

        result = []
        for sub in submissions:
            result.append({
                'id': sub.id,
                'user_name': f"{sub.user.first_name} {sub.user.last_name}",
                'archive_name': sub.archive.name if sub.archive else 'N/A',
                'status': sub.status,
                'upload_date': sub.upload_date.strftime('%d/%m/%Y %H:%M') if sub.upload_date else 'N/A'
            })

        return result

    @staticmethod
    def get_combined_program_metrics(program_ids):
        """
        Obtiene métricas combinadas para múltiples programas

        Args:
            program_ids: Lista de IDs de programas

        Returns:
            dict con métricas combinadas
        """
        if not program_ids:
            return {
                'total_applicants': 0,
                'pending_reviews': 0,
                'approved_applications': 0,
                'rejected_applications': 0,
                'interviews_scheduled': 0,
                'total_submissions': 0,
                'in_process': 0
            }

        # Total de solicitantes en los programas seleccionados
        total_applicants = db.session.query(func.count(UserProgram.user_id)).filter(
            UserProgram.program_id.in_(program_ids),
            UserProgram.status.in_(['pending', 'active'])
        ).scalar() or 0

        # Documentos pendientes de revisión en todos los programas
        pending_reviews = db.session.query(func.count(Submission.id)).join(
            ProgramStep, Submission.program_step_id == ProgramStep.id
        ).filter(
            ProgramStep.program_id.in_(program_ids),
            Submission.status == 'review'
        ).scalar() or 0

        # Total de submissions en todos los programas
        total_submissions = db.session.query(func.count(Submission.id)).join(
            ProgramStep, Submission.program_step_id == ProgramStep.id
        ).filter(
            ProgramStep.program_id.in_(program_ids)
        ).scalar() or 0

        # Calcular aprobados y rechazados
        approved_count = 0
        rejected_count = 0

        for program_id in program_ids:
            applicants = db.session.query(UserProgram).filter(
                UserProgram.program_id == program_id,
                UserProgram.status == 'pending'
            ).all()

            for applicant in applicants:
                submissions = db.session.query(Submission).join(
                    ProgramStep, Submission.program_step_id == ProgramStep.id
                ).filter(
                    Submission.user_id == applicant.user_id,
                    ProgramStep.program_id == program_id
                ).all()

                if submissions:
                    all_approved = all(s.status == 'approved' for s in submissions)
                    has_rejected = any(s.status == 'rejected' for s in submissions)

                    if all_approved:
                        approved_count += 1
                    elif has_rejected:
                        rejected_count += 1

        # Entrevistas programadas en todos los programas
        from app.models.event import EventWindow
        interviews_scheduled = db.session.query(func.count(EventSlot.id)).join(
            EventWindow, EventSlot.event_window_id == EventWindow.id
        ).join(
            Event, EventWindow.event_id == Event.id
        ).filter(
            Event.program_id.in_(program_ids),
            Event.type == 'interview',
            EventSlot.status == 'booked'
        ).scalar() or 0

        return {
            'total_applicants': total_applicants,
            'pending_reviews': pending_reviews,
            'approved_applications': approved_count,
            'rejected_applications': rejected_count,
            'interviews_scheduled': interviews_scheduled,
            'total_submissions': total_submissions,
            'in_process': total_applicants - approved_count - rejected_count
        }

    @staticmethod
    def get_recent_submissions_multiple(program_ids, limit=5):
        """
        Obtiene las últimas submissions para múltiples programas

        Args:
            program_ids: Lista de IDs de programas
            limit: Número máximo de submissions a retornar

        Returns:
            list de submissions recientes con nombre del programa
        """
        if not program_ids:
            return []

        submissions = db.session.query(Submission).join(
            ProgramStep, Submission.program_step_id == ProgramStep.id
        ).join(
            Program, ProgramStep.program_id == Program.id
        ).join(
            User, Submission.user_id == User.id
        ).filter(
            ProgramStep.program_id.in_(program_ids),
            Submission.status.in_(['review', 'pending'])
        ).order_by(
            Submission.upload_date.desc()
        ).limit(limit).all()

        result = []
        for sub in submissions:
            result.append({
                'id': sub.id,
                'user_name': f"{sub.user.first_name} {sub.user.last_name}",
                'archive_name': sub.archive.name if sub.archive else 'N/A',
                'program_name': sub.program_step.program.name,
                'status': sub.status,
                'upload_date': sub.upload_date.strftime('%d/%m/%Y %H:%M') if sub.upload_date else 'N/A'
            })

        return result

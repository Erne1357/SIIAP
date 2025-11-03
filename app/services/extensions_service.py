# app/services/extensions_service.py - Actualizado
from datetime import datetime, timezone
from app.utils.datetime_utils import now_local
from sqlalchemy.exc import IntegrityError
from app import db
from app.models.extension_request import ExtensionRequest
from app.models.archive import Archive
from app.models.program_step import ProgramStep
from app.models.user_program import UserProgram

class ExtensionsService:
    @staticmethod
    def create_request(user_id: int, archive_id: int, requested_by: int, reason: str, requested_until, role: str = 'student') -> ExtensionRequest:
        """
        Crea una solicitud de prórroga para un archivo específico.
        Ya no requiere que exista una submission previa.
        """
        # Validar que el archivo existe
        archive = db.session.get(Archive, archive_id)
        if not archive:
            raise ValueError("Archivo no encontrado")
        
        # Encontrar el program_step correspondiente al usuario
        # Asumimos que el usuario está inscrito en el programa donde está el step del archive
        user_program = UserProgram.query.filter_by(user_id=user_id).first()
        if not user_program:
            raise ValueError("Usuario no inscrito en ningún programa")
        
        program_step = ProgramStep.query.filter_by(
            program_id=user_program.program_id,
            step_id=archive.step_id
        ).first()
        
        if not program_step:
            raise ValueError("El archivo no pertenece al programa del usuario")
        
        # Verificar que no haya una solicitud pendiente para el mismo archivo
        existing = ExtensionRequest.query.filter_by(
            user_id=user_id,
            archive_id=archive_id,
            status='pending'
        ).first()
        
        if existing:
            raise ValueError("Ya tienes una solicitud pendiente para este archivo")
        
        er = ExtensionRequest(
            user_id=user_id,
            archive_id=archive_id,
            program_step_id=program_step.id,
            requested_by=requested_by,
            reason=reason,
            requested_until=requested_until,
            role=role
        )
        
        db.session.add(er)
        db.session.commit()
        return er

    @staticmethod
    def list_requests(user_id=None, archive_id=None, status=None, program_id=None):
        """Lista solicitudes de prórroga con filtros opcionales"""
        query = db.session.query(ExtensionRequest).join(Archive)
        
        if user_id:
            query = query.filter(ExtensionRequest.user_id == user_id)
        if archive_id:
            query = query.filter(ExtensionRequest.archive_id == archive_id)
        if status:
            query = query.filter(ExtensionRequest.status == status)
        if program_id:
            query = query.join(ProgramStep).filter(ProgramStep.program_id == program_id)
        
        return query.order_by(ExtensionRequest.created_at.desc()).all()

    @staticmethod
    def decide_request(request_id: int, status: str, decided_by: int, granted_until=None, condition_text=None) -> ExtensionRequest:
        """Decide sobre una solicitud de prórroga"""
        er = db.session.get(ExtensionRequest, request_id)
        if not er:
            raise ValueError("Solicitud de extensión no encontrada")

        if status not in ('granted', 'rejected', 'cancelled'):
            raise ValueError("Estado inválido")

        er.status = status
        er.decided_by = decided_by
        er.decided_at = now_local()
        er.updated_at = now_local()
        er.granted_until = granted_until
        er.condition_text = condition_text

        db.session.commit()
        return er

    @staticmethod
    def get_active_extension(user_id: int, archive_id: int) -> ExtensionRequest | None:
        """Obtiene la prórroga activa (granted) para un usuario y archivo específico"""
        return ExtensionRequest.query.filter_by(
            user_id=user_id,
            archive_id=archive_id,
            status='granted'
        ).first()

    @staticmethod
    def has_pending_request(user_id: int, archive_id: int) -> bool:
        """Verifica si hay una solicitud pendiente para un archivo"""
        return db.session.query(
            ExtensionRequest.query.filter_by(
                user_id=user_id,
                archive_id=archive_id,
                status='pending'
            ).exists()
        ).scalar()

    @staticmethod
    def get_effective_deadline(user_id: int, archive_id: int) -> datetime | None:
        """
        Obtiene la fecha límite efectiva para un archivo.
        Si hay una prórroga granted, devuelve esa fecha.
        Si no, devuelve None (usar deadline por defecto del programa).
        """
        extension = ExtensionsService.get_active_extension(user_id, archive_id)
        return extension.granted_until if extension else None
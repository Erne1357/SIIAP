# app/services/user_history_service.py

from app import db
from app.models.user_history import UserHistory
from app.models.user import User
from flask_login import current_user
from typing import Optional, Dict, Any, List
import json


class UserHistoryService:
    """
    Servicio para gestionar el historial de acciones administrativas sobre usuarios.
    Centraliza toda la lógica relacionada con el registro y consulta del historial.
    """

    @staticmethod
    def log_action(
        user_id: int, 
        action: str, 
        details: Optional[str | Dict[str, Any]] = None, 
        admin_id: Optional[int] = None
    ) -> UserHistory:
        """
        Registra una acción en el historial del usuario.
        
        Args:
            user_id: ID del usuario afectado por la acción
            action: Tipo de acción realizada (ver ACTIONS para valores válidos)
            details: Detalles adicionales de la acción (string o dict)
            admin_id: ID del administrador que realizó la acción (opcional, usa current_user si no se especifica)
            
        Returns:
            UserHistory: La entrada de historial creada
            
        Raises:
            ValueError: Si el action no es válido o el user_id no existe
        """
        # Validar que el usuario existe
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"Usuario con ID {user_id} no existe")
        
        # Validar acción
        if action not in UserHistoryService.ACTIONS:
            raise ValueError(f"Acción '{action}' no es válida. Acciones permitidas: {list(UserHistoryService.ACTIONS.keys())}")
        
        # Convertir details a JSON si es un diccionario
        if isinstance(details, dict):
            details = json.dumps(details, ensure_ascii=False)
        
        # Usar current_user si no se especifica admin_id
        if admin_id is None and current_user.is_authenticated:
            admin_id = current_user.id
        
        # Crear entrada de historial
        history_entry = UserHistory(
            user_id=user_id,
            admin_id=admin_id,
            action=action,
            details=details
        )
        
        db.session.add(history_entry)
        return history_entry

    @staticmethod
    def log_password_reset(user_id: int, admin_id: Optional[int] = None) -> UserHistory:
        """Registra un reset de contraseña"""
        admin_name = "Sistema"
        if admin_id:
            admin = User.query.get(admin_id)
            if admin:
                admin_name = f"{admin.first_name} {admin.last_name}"
        elif current_user.is_authenticated:
            admin_name = f"{current_user.first_name} {current_user.last_name}"
        
        return UserHistoryService.log_action(
            user_id=user_id,
            action='password_reset',
            details=f"Contraseña reseteada por {admin_name}",
            admin_id=admin_id
        )

    @staticmethod
    def log_password_change(user_id: int, changed_by_user: bool = True) -> UserHistory:
        """Registra un cambio de contraseña"""
        details = "Contraseña cambiada por el usuario" if changed_by_user else "Contraseña cambiada por administrador"
        
        return UserHistoryService.log_action(
            user_id=user_id,
            action='password_changed',
            details=details,
            admin_id=None if changed_by_user else (current_user.id if current_user.is_authenticated else None)
        )

    @staticmethod
    def log_user_activation(user_id: int, is_active: bool, admin_id: Optional[int] = None) -> UserHistory:
        """Registra activación/desactivación de usuario"""
        admin_name = "Sistema"
        if admin_id:
            admin = User.query.get(admin_id)
            if admin:
                admin_name = f"{admin.first_name} {admin.last_name}"
        elif current_user.is_authenticated:
            admin_name = f"{current_user.first_name} {current_user.last_name}"
        
        action = 'activated' if is_active else 'deactivated'
        status = 'activado' if is_active else 'desactivado'
        
        return UserHistoryService.log_action(
            user_id=user_id,
            action=action,
            details=f"Usuario {status} por {admin_name}",
            admin_id=admin_id
        )

    @staticmethod
    def log_control_number_assignment(
        user_id: int, 
        control_number: str, 
        old_username: str, 
        program_name: str, 
        admin_id: Optional[int] = None
    ) -> UserHistory:
        """Registra asignación de número de control"""
        details = {
            'control_number': control_number,
            'old_username': old_username,
            'program': program_name
        }
        
        return UserHistoryService.log_action(
            user_id=user_id,
            action='control_number_assigned',
            details=details,
            admin_id=admin_id
        )

    @staticmethod
    def log_basic_info_update(user_id: int, changed_fields: Dict[str, Dict[str, str]], admin_id: Optional[int] = None) -> UserHistory:
        """Registra actualización de información básica"""
        return UserHistoryService.log_action(
            user_id=user_id,
            action='basic_info_updated',
            details=changed_fields,
            admin_id=admin_id
        )

    @staticmethod
    def log_profile_completion(user_id: int) -> UserHistory:
        """Registra cuando un usuario completa su perfil"""
        return UserHistoryService.log_action(
            user_id=user_id,
            action='profile_completed',
            details="Perfil completado por el usuario",
            admin_id=None
        )

    @staticmethod
    def log_role_change(user_id: int, old_role: str, new_role: str, admin_id: Optional[int] = None) -> UserHistory:
        """Registra cambio de rol"""
        details = {
            'old_role': old_role,
            'new_role': new_role
        }
        
        return UserHistoryService.log_action(
            user_id=user_id,
            action='role_changed',
            details=details,
            admin_id=admin_id
        )

    @staticmethod
    def log_user_creation(user_id: int, created_by_admin: bool = False, admin_id: Optional[int] = None) -> UserHistory:
        """Registra creación de usuario"""
        details = "Usuario creado por administrador" if created_by_admin else "Usuario registrado en el sistema"
        
        return UserHistoryService.log_action(
            user_id=user_id,
            action='created',
            details=details,
            admin_id=admin_id if created_by_admin else None
        )

    @staticmethod
    def log_user_deletion(user_id: int, user_name: str, admin_id: Optional[int] = None) -> UserHistory:
        """Registra eliminación de usuario (se debe llamar ANTES de eliminar)"""
        admin_name = "Sistema"
        if admin_id:
            admin = User.query.get(admin_id)
            if admin:
                admin_name = f"{admin.first_name} {admin.last_name}"
        elif current_user.is_authenticated:
            admin_name = f"{current_user.first_name} {current_user.last_name}"
        
        return UserHistoryService.log_action(
            user_id=user_id,
            action='deleted',
            details=f"Usuario {user_name} eliminado por {admin_name}",
            admin_id=admin_id
        )

    @staticmethod
    def get_user_history(
        user_id: int, 
        limit: Optional[int] = None, 
        action_filter: Optional[str] = None,
        order_by: Optional[str] = None
    ) -> List[UserHistory]:
        """
        Obtiene el historial de un usuario.
        
        Args:
            user_id: ID del usuario
            limit: Número máximo de entradas a retornar
            action_filter: Filtrar por tipo de acción específica
            
        Returns:
            Lista de entradas del historial ordenadas por fecha (más reciente primero)
        """
        query = UserHistory.query.filter_by(user_id=user_id)
        
        if order_by.lower() == 'desc':
            query = query.order_by(UserHistory.timestamp.desc())
        else:
            query = query.order_by(UserHistory.timestamp.asc())

        if action_filter:
            query = query.filter(UserHistory.action == action_filter)
        
        query = query.order_by(UserHistory.timestamp.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()

    @staticmethod
    def get_recent_activity(limit: int = 50) -> List[UserHistory]:
        """
        Obtiene la actividad reciente de todos los usuarios.
        
        Args:
            limit: Número máximo de entradas a retornar
            
        Returns:
            Lista de entradas del historial ordenadas por fecha (más reciente primero)
        """
        return UserHistory.query.order_by(UserHistory.timestamp.desc()).limit(limit).all()

    @staticmethod
    def get_admin_activity(admin_id: int, limit: Optional[int] = None) -> List[UserHistory]:
        """
        Obtiene todas las acciones realizadas por un administrador específico.
        
        Args:
            admin_id: ID del administrador
            limit: Número máximo de entradas a retornar
            
        Returns:
            Lista de entradas del historial ordenadas por fecha (más reciente primero)
        """
        query = UserHistory.query.filter_by(admin_id=admin_id).order_by(UserHistory.timestamp.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()

    # ==================== POSTULACIONES Y PROGRAMAS ====================
    @staticmethod
    def log_program_enrollment(user_id: int, program_name: str, program_id: int) -> 'UserHistory':
        """Registra postulación a un programa"""
        details = {
            'program_id': program_id,
            'program_name': program_name,
            'action_type': 'enrollment'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='program_enrolled',
            details=details,
            admin_id=None  # Acción del usuario
        )

    @staticmethod
    def log_program_transfer_request(user_id: int, from_program: str, to_program: str, reason: str) -> 'UserHistory':
        """Registra solicitud de cambio de programa"""
        details = {
            'from_program': from_program,
            'to_program': to_program,
            'reason': reason,
            'action_type': 'transfer_request'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='program_transfer_requested',
            details=details,
            admin_id=None
        )

    @staticmethod
    def log_program_transfer_execution(user_id: int, from_program: str, to_program: str, 
                                     documents_moved: int, documents_lost: int) -> 'UserHistory':
        """Registra ejecución de cambio de programa"""
        details = {
            'from_program': from_program,
            'to_program': to_program,
            'documents_moved': documents_moved,
            'documents_lost': documents_lost,
            'action_type': 'transfer_executed'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='program_transferred',
            details=details,
            admin_id=None
        )

    # ==================== DOCUMENTOS ====================
    @staticmethod
    def log_document_upload(user_id: int, archive_name: str, program_name: str, 
                          uploaded_by_admin: bool = False, admin_id: int = None) -> 'UserHistory':
        """Registra subida de documento"""
        details = {
            'archive_name': archive_name,
            'program_name': program_name,
            'uploaded_by_admin': uploaded_by_admin,
            'action_type': 'document_upload'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='document_uploaded',
            details=details,
            admin_id=admin_id if uploaded_by_admin else None
        )

    @staticmethod
    def log_document_deletion(user_id: int, archive_name: str, program_name: str, 
                            deleted_by_admin: bool = False, admin_id: int = None) -> 'UserHistory':
        """Registra eliminación de documento"""
        details = {
            'archive_name': archive_name,
            'program_name': program_name,
            'deleted_by_admin': deleted_by_admin,
            'action_type': 'document_deletion'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='document_deleted',
            details=details,
            admin_id=admin_id if deleted_by_admin else None
        )

    @staticmethod
    def log_document_review(user_id: int, archive_name: str, status: str, 
                          reviewer_comment: str = None, admin_id: int = None) -> 'UserHistory':
        """Registra revisión de documento (aprobar/rechazar)"""
        details = {
            'archive_name': archive_name,
            'review_status': status,
            'reviewer_comment': reviewer_comment,
            'action_type': 'document_review'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='document_reviewed',
            details=details,
            admin_id=admin_id
        )

    # ==================== PRÓRROGAS ====================
    @staticmethod
    def log_extension_request(user_id: int, archive_name: str, requested_until: str, 
                            reason: str, requested_by_admin: bool = False, admin_id: int = None) -> 'UserHistory':
        """Registra solicitud de prórroga"""
        details = {
            'archive_name': archive_name,
            'requested_until': requested_until,
            'reason': reason,
            'requested_by_admin': requested_by_admin,
            'action_type': 'extension_request'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='extension_requested',
            details=details,
            admin_id=admin_id if requested_by_admin else None
        )

    @staticmethod
    def log_extension_decision(user_id: int, archive_name: str, decision: str, 
                             granted_until: str = None, condition_text: str = None, admin_id: int = None) -> 'UserHistory':
        """Registra decisión sobre prórroga"""
        details = {
            'archive_name': archive_name,
            'decision': decision,
            'granted_until': granted_until,
            'condition_text': condition_text,
            'action_type': 'extension_decision'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='extension_decided',
            details=details,
            admin_id=admin_id
        )

    # ==================== EVENTOS Y CITAS ====================
    @staticmethod
    def log_event_registration(user_id: int, event_title: str, event_type: str) -> 'UserHistory':
        """Registra registro a evento"""
        details = {
            'event_title': event_title,
            'event_type': event_type,
            'action_type': 'event_registration'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='event_registered',
            details=details,
            admin_id=None
        )

    @staticmethod
    def log_appointment_assignment(user_id: int, event_title: str, appointment_datetime: str, 
                                 assigned_by_admin: int = None) -> 'UserHistory':
        """Registra asignación de cita"""
        details = {
            'event_title': event_title,
            'appointment_datetime': appointment_datetime,
            'action_type': 'appointment_assignment'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='appointment_assigned',
            details=details,
            admin_id=assigned_by_admin
        )

    @staticmethod
    def log_appointment_cancellation(user_id: int, event_title: str, reason: str, 
                                   cancelled_by_admin: bool = False, admin_id: int = None) -> 'UserHistory':
        """Registra cancelación de cita"""
        details = {
            'event_title': event_title,
            'reason': reason,
            'cancelled_by_admin': cancelled_by_admin,
            'action_type': 'appointment_cancellation'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='appointment_cancelled',
            details=details,
            admin_id=admin_id if cancelled_by_admin else None
        )

    # ==================== RETENCIÓN Y LIMPIEZA ====================
    @staticmethod
    def log_document_purged(user_id: int, archive_name: str, reason: str, admin_id: int = None) -> 'UserHistory':
        """Registra eliminación de documento por políticas de retención"""
        details = {
            'archive_name': archive_name,
            'reason': reason,
            'action_type': 'document_purged'
        }
        return UserHistoryService.log_action(
            user_id=user_id,
            action='document_purged',
            details=details,
            admin_id=admin_id
        )

    # ==================== CRITERIOS PARA ACCIONES CRÍTICAS ====================
    
    # Acciones críticas que NUNCA se deben eliminar (tienen implicaciones legales/académicas)
    CRITICAL_ACTIONS = {
        # Gestión académica crítica
        'control_number_assigned',  # Asignación oficial de matrícula
        'program_transferred',      # Cambios de programa oficiales
        'program_enrolled',         # Inscripciones iniciales
        
        # Decisiones administrativas importantes
        'extension_decided',        # Decisiones de prórrogas (pueden ser legales)
        'document_purged',          # Eliminaciones por retención (auditoría)
        'role_changed',            # Cambios de permisos/acceso
        
        # Acciones irreversibles del sistema
        'deleted',                 # Eliminaciones de usuarios
        'document_reviewed',       # Decisiones de revisión de documentos
        
        # Seguridad y acceso
        'deactivated',            # Desactivaciones (pueden ser disciplinarias)
        'activated'               # Reactivaciones importantes
    }
    
    # Acciones de alta importancia (conservar por más tiempo)
    HIGH_IMPORTANCE_ACTIONS = {
        'password_reset',         # Importante para seguridad
        'basic_info_updated',     # Cambios de datos personales
        'document_uploaded',      # Historial de documentación
        'document_deleted',       # Eliminaciones de documentos
        'appointment_assigned',   # Asignaciones de citas importantes
        'program_transfer_requested'  # Solicitudes de cambio
    }
    
    # Acciones de importancia media (limpieza normal)
    MEDIUM_IMPORTANCE_ACTIONS = {
        'password_changed',       # Cambios rutinarios
        'profile_updated',        # Actualizaciones de perfil
        'profile_completed',      # Completar perfil
        'event_registered',       # Registros a eventos
        'extension_requested',    # Solicitudes de prórroga
        'appointment_cancelled'   # Cancelaciones de citas
    }

    # Constantes para los tipos de acciones válidas
    ACTIONS = {
        # Acciones originales
        'password_reset': 'Contraseña restablecida',
        'password_changed': 'Contraseña cambiada',
        'deactivated': 'Usuario desactivado',
        'activated': 'Usuario activado',
        'control_number_assigned': 'Número de control asignado',
        'role_changed': 'Rol modificado',
        'profile_updated': 'Perfil actualizado',
        'deleted': 'Usuario eliminado',
        'created': 'Usuario creado',
        'basic_info_updated': 'Información básica actualizada',
        'profile_completed': 'Perfil completado',
        
        # Nuevas acciones - Programas
        'program_enrolled': 'Postulado a programa',
        'program_transfer_requested': 'Solicitud de cambio de programa',
        'program_transferred': 'Cambio de programa ejecutado',
        
        # Nuevas acciones - Documentos
        'document_uploaded': 'Documento subido',
        'document_deleted': 'Documento eliminado',
        'document_reviewed': 'Documento revisado',
        'document_purged': 'Documento eliminado por retención',
        
        # Nuevas acciones - Prórrogas
        'extension_requested': 'Prórroga solicitada',
        'extension_decided': 'Prórroga decidida',
        
        # Nuevas acciones - Eventos y Citas
        'event_registered': 'Registrado a evento',
        'appointment_assigned': 'Cita asignada',
        'appointment_cancelled': 'Cita cancelada',
    }

    @staticmethod
    def get_action_label(action: str) -> str:
        """
        Obtiene la etiqueta legible para una acción.
        
        Args:
            action: Código de la acción
            
        Returns:
            Etiqueta legible de la acción
        """
        return UserHistoryService.ACTIONS.get(action, action)

    @staticmethod
    def is_critical_action(action: str) -> bool:
        """
        Determina si una acción es crítica y nunca debe eliminarse.
        
        Args:
            action: Código de la acción
            
        Returns:
            True si es crítica, False en caso contrario
        """
        return action in UserHistoryService.CRITICAL_ACTIONS

    @staticmethod
    def get_action_importance_level(action: str) -> str:
        """
        Obtiene el nivel de importancia de una acción.
        
        Args:
            action: Código de la acción
            
        Returns:
            'critical', 'high', 'medium', o 'low'
        """
        if action in UserHistoryService.CRITICAL_ACTIONS:
            return 'critical'
        elif action in UserHistoryService.HIGH_IMPORTANCE_ACTIONS:
            return 'high'
        elif action in UserHistoryService.MEDIUM_IMPORTANCE_ACTIONS:
            return 'medium'
        else:
            return 'low'

    @staticmethod
    def get_retention_policy_for_action(action: str) -> dict:
        """
        Obtiene la política de retención recomendada para una acción.
        
        Args:
            action: Código de la acción
            
        Returns:
            Diccionario con la política de retención
        """
        importance = UserHistoryService.get_action_importance_level(action)
        
        policies = {
            'critical': {
                'retention_years': -1,  # Permanente
                'description': 'Conservar permanentemente por implicaciones legales/académicas'
            },
            'high': {
                'retention_years': 10,
                'description': 'Conservar 10 años por alta importancia'
            },
            'medium': {
                'retention_years': 5,
                'description': 'Conservar 5 años por importancia media'
            },
            'low': {
                'retention_years': 2,
                'description': 'Conservar 2 años por baja importancia'
            }
        }
        
        return policies.get(importance, policies['low'])
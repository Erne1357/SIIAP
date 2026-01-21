# app/services/history_retention_service.py
"""
Servicio para la limpieza automática del historial de usuarios
basado en políticas de retención configurables.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import and_, or_
from app import db
from app.models.user_history import UserHistory
from app.models.user import User
from app.models.user_program import UserProgram
from app.utils.datetime_utils import now_local


class HistoryRetentionService:
    """
    Gestiona la retención y limpieza del historial de usuarios
    """
    
    # Acciones críticas que NUNCA se deben eliminar
    CRITICAL_ACTIONS = {
        'control_number_assigned',
        'program_transferred', 
        'document_purged',
        'deleted',
        'role_changed',
        'program_enrolled',
        'extension_decided'  # Decisiones importantes de prórrogas
    }
    
    # Configuración por defecto (en años)
    DEFAULT_RETENTION = {
        'active_users': 3,      # Usuarios activos: 3 años
        'graduated_users': 7,   # Graduados: 7 años  
        'inactive_users': 2,    # Inactivos: 2 años
        'critical_actions': -1  # Acciones críticas: permanente (-1)
    }

    @staticmethod
    def cleanup_old_history(dry_run: bool = True, retention_config: Optional[Dict] = None) -> Dict:
        """
        Limpia el historial antiguo basado en las políticas de retención.
        
        Args:
            dry_run: Si es True, solo simula la limpieza sin eliminar
            retention_config: Configuración personalizada de retención (opcional)
            
        Returns:
            Estadísticas de la limpieza realizada
        """
        config = retention_config or HistoryRetentionService.DEFAULT_RETENTION
        now = now_local()
        stats = {
            'total_entries_analyzed': 0,
            'entries_to_delete': 0,
            'entries_preserved_critical': 0,
            'entries_deleted': 0,
            'users_affected': set(),
            'oldest_entry_kept': None,
            'dry_run': dry_run
        }
        
        # 1. Obtener todos los usuarios y clasificarlos
        users_status = HistoryRetentionService._classify_users()
        
        # 2. Para cada categoría de usuario, aplicar políticas
        for user_status, user_ids in users_status.items():
            if not user_ids:
                continue
                
            retention_years = config.get(f"{user_status}_users", config['active_users'])
            if retention_years == -1:  # Permanente
                continue
                
            cutoff_date = now - timedelta(days=retention_years * 365)
            
            # 3. Encontrar entradas a eliminar (excluyendo acciones críticas)
            entries_to_delete = db.session.query(UserHistory).filter(
                and_(
                    UserHistory.user_id.in_(user_ids),
                    UserHistory.timestamp < cutoff_date,
                    ~UserHistory.action.in_(HistoryRetentionService.CRITICAL_ACTIONS)
                )
            ).all()
            
            stats['total_entries_analyzed'] += len(entries_to_delete)
            stats['entries_to_delete'] += len(entries_to_delete)
            stats['users_affected'].update(user_ids)
            
            # 4. Eliminar o simular eliminación
            if not dry_run and entries_to_delete:
                for entry in entries_to_delete:
                    db.session.delete(entry)
                stats['entries_deleted'] += len(entries_to_delete)
        
        # 5. Contar acciones críticas preservadas
        critical_count = db.session.query(UserHistory).filter(
            UserHistory.action.in_(HistoryRetentionService.CRITICAL_ACTIONS)
        ).count()
        stats['entries_preserved_critical'] = critical_count
        
        # 6. Obtener fecha de la entrada más antigua conservada
        oldest_entry = db.session.query(UserHistory).order_by(UserHistory.timestamp.asc()).first()
        if oldest_entry:
            stats['oldest_entry_kept'] = oldest_entry.timestamp.isoformat()
        
        # 7. Commit si no es dry run
        if not dry_run:
            db.session.commit()
        
        stats['users_affected'] = len(stats['users_affected'])
        return stats

    @staticmethod
    def _classify_users() -> Dict[str, List[int]]:
        """
        Clasifica usuarios según su estado actual.
        
        Returns:
            Diccionario con listas de user_ids por categoría
        """
        from sqlalchemy import select, case, func
        
        # Query compleja para clasificar usuarios
        subquery = db.session.query(
            User.id,
            User.is_active,
            func.max(UserProgram.graduation_date).label('graduation_date'),
            func.count(UserProgram.id).label('program_count')
        ).outerjoin(UserProgram, User.id == UserProgram.user_id).group_by(User.id, User.is_active).subquery()
        
        results = db.session.query(subquery).all()
        
        classification = {
            'active': [],
            'graduated': [],
            'inactive': []
        }
        
        now = now_local()
        
        for user_data in results:
            user_id = user_data.id
            is_active = user_data.is_active
            graduation_date = user_data.graduation_date
            program_count = user_data.program_count or 0
            
            # Lógica de clasificación
            if not is_active:
                classification['inactive'].append(user_id)
            elif graduation_date and graduation_date <= now:
                classification['graduated'].append(user_id)
            elif program_count > 0:
                classification['active'].append(user_id)
            else:
                classification['inactive'].append(user_id)
        
        return classification

    @staticmethod
    def get_retention_statistics() -> Dict:
        """
        Obtiene estadísticas actuales del historial.
        
        Returns:
            Estadísticas detalladas del historial
        """
        from sqlalchemy import func, extract
        
        stats = {}
        
        # Total de entradas
        total_entries = db.session.query(func.count(UserHistory.id)).scalar()
        stats['total_entries'] = total_entries
        
        # Entradas por año
        entries_by_year = db.session.query(
            extract('year', UserHistory.timestamp).label('year'),
            func.count(UserHistory.id).label('count')
        ).group_by(extract('year', UserHistory.timestamp)).all()
        
        stats['entries_by_year'] = {int(year): count for year, count in entries_by_year}
        
        # Acciones más comunes
        top_actions = db.session.query(
            UserHistory.action,
            func.count(UserHistory.id).label('count')
        ).group_by(UserHistory.action).order_by(func.count(UserHistory.id).desc()).limit(10).all()
        
        stats['top_actions'] = [(action, count) for action, count in top_actions]
        
        # Entrada más antigua y más reciente
        oldest = db.session.query(func.min(UserHistory.timestamp)).scalar()
        newest = db.session.query(func.max(UserHistory.timestamp)).scalar()
        
        stats['oldest_entry'] = oldest.isoformat() if oldest else None
        stats['newest_entry'] = newest.isoformat() if newest else None
        
        # Acciones críticas preservadas
        critical_count = db.session.query(func.count(UserHistory.id)).filter(
            UserHistory.action.in_(HistoryRetentionService.CRITICAL_ACTIONS)
        ).scalar()
        
        stats['critical_actions_count'] = critical_count
        stats['critical_actions_percentage'] = round((critical_count / total_entries * 100) if total_entries > 0 else 0, 2)
        
        return stats

    @staticmethod
    def schedule_cleanup_job():
        """
        Configura un trabajo programado para la limpieza automática.
        Esto requeriría un sistema de colas como Celery.
        """
        # Esta función sería implementada con Celery o similar
        # Para ejecutar la limpieza automáticamente
        pass
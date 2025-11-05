# app/utils/history_formatter.py
"""
Utilidades para formatear y normalizar los detalles del historial de usuarios
para mostrarlos de manera más legible y en español.
"""

import json
from typing import Dict, Any, Optional


class HistoryFormatter:
    """
    Clase para formatear los detalles del historial de usuarios
    de manera más legible y en español.
    """
    
    @staticmethod
    def format_details(action: str, details: Optional[str]) -> str:
        """
        Formatea los detalles de una acción del historial para mostrarlos
        de manera más legible en español.
        
        Args:
            action: El tipo de acción (ej: 'program_transferred')
            details: Los detalles en formato JSON string o string simple
            
        Returns:
            String formateado en español
        """
        if not details:
            return HistoryFormatter._get_default_message(action)
        
        # Intentar parsear como JSON
        parsed_details = HistoryFormatter._parse_details(details)
        
        # Formatear según el tipo de acción
        formatter_method = f"_format_{action}"
        if hasattr(HistoryFormatter, formatter_method):
            return getattr(HistoryFormatter, formatter_method)(parsed_details)
        else:
            return HistoryFormatter._format_generic(action, parsed_details)
    
    @staticmethod
    def _parse_details(details: str) -> Dict[str, Any]:
        """Intenta parsear los detalles como JSON, sino los devuelve como string."""
        if isinstance(details, dict):
            return details
        
        try:
            return json.loads(details)
        except (json.JSONDecodeError, TypeError):
            return {"raw": details}
    
    @staticmethod
    def _get_default_message(action: str) -> str:
        """Mensajes por defecto para acciones sin detalles."""
        default_messages = {
            'password_reset': 'Contraseña restablecida',
            'password_changed': 'Contraseña actualizada',
            'deactivated': 'Usuario desactivado',
            'activated': 'Usuario activado',
            'profile_completed': 'Perfil completado exitosamente',
            'created': 'Usuario creado en el sistema',
            'deleted': 'Usuario eliminado',
            'program_enrolled': 'Inscrito a un programa',
            'event_registered': 'Registrado a un evento',
        }
        return default_messages.get(action, f"Acción realizada: {action}")
    
    # ==================== FORMATTERS ESPECÍFICOS ====================
    
    @staticmethod
    def _format_program_enrolled(details: Dict[str, Any]) -> str:
        """Formato: 'Inscrito al programa [Nombre del Programa]'"""
        program_name = details.get('program_name', 'programa desconocido')
        return f"Inscrito al programa {program_name}"
    
    @staticmethod
    def _format_program_transfer_requested(details: Dict[str, Any]) -> str:
        """Formato: 'Solicitó cambio de [Programa A] a [Programa B]'"""
        from_program = details.get('from_program', 'programa desconocido')
        to_program = details.get('to_program', 'programa desconocido')
        reason = details.get('reason', '')
        
        message = f"Solicitó cambio de {from_program} a {to_program}"
        if reason:
            message += f" (Motivo: {reason})"
        return message
    
    @staticmethod
    def _format_program_transferred(details: Dict[str, Any]) -> str:
        """Formato: 'Cambio de programa completado de [A] a [B]. X documentos transferidos, Y perdidos'"""
        from_program = details.get('from_program', 'programa anterior')
        to_program = details.get('to_program', 'programa nuevo')
        docs_moved = details.get('documents_moved', 0)
        docs_lost = details.get('documents_lost', 0)
        
        message = f"Cambio de programa completado: de {from_program} a {to_program}"
        
        if docs_moved > 0 or docs_lost > 0:
            message += f". {docs_moved} documentos transferidos"
            if docs_lost > 0:
                message += f", {docs_lost} documentos perdidos"
        
        return message
    
    @staticmethod
    def _format_document_uploaded(details: Dict[str, Any]) -> str:
        """Formato: 'Subió documento [Nombre] para [Programa]'"""
        archive_name = details.get('archive_name', 'documento')
        program_name = details.get('program_name', 'programa')
        uploaded_by_admin = details.get('uploaded_by_admin', False)
        
        if uploaded_by_admin:
            return f"Coordinador subió documento '{archive_name}' del programa {program_name}"
        else:
            return f"Subió documento '{archive_name}' para {program_name}"
    
    @staticmethod
    def _format_document_deleted(details: Dict[str, Any]) -> str:
        """Formato: 'Eliminó documento [Nombre] de [Programa]'"""
        archive_name = details.get('archive_name', 'documento')
        program_name = details.get('program_name', 'programa')
        deleted_by_admin = details.get('deleted_by_admin', False)
        
        if deleted_by_admin:
            return f"Coordinador eliminó documento '{archive_name}' del programa {program_name}"
        else:
            return f"Eliminó documento '{archive_name}' de {program_name}"
    
    @staticmethod
    def _format_document_reviewed(details: Dict[str, Any]) -> str:
        """Formato: 'Documento [Nombre] fue [aprobado/rechazado]'"""
        archive_name = details.get('archive_name', 'documento')
        status = details.get('review_status', 'revisado')
        comment = details.get('reviewer_comment', '')
        
        status_text = {
            'approved': 'aprobado',
            'rejected': 'rechazado',
            'pending': 'puesto en revisión'
        }.get(status, status)
        
        message = f"Documento '{archive_name}' fue {status_text}"
        if comment:
            message += f" (Comentario: {comment})"
        return message
    
    @staticmethod
    def _format_document_purged(details: Dict[str, Any]) -> str:
        """Formato: 'Documento [Nombre] eliminado por política de retención'"""
        archive_name = details.get('archive_name', 'documento')
        reason = details.get('reason', 'política de retención')
        return f"Documento '{archive_name}' eliminado por {reason}"
    
    @staticmethod
    def _format_extension_requested(details: Dict[str, Any]) -> str:
        """Formato: 'Solicitó prórroga para [Documento] hasta [Fecha]'"""
        archive_name = details.get('archive_name', 'documento')
        requested_until = details.get('requested_until', 'fecha no especificada')
        reason = details.get('reason', '')
        requested_by_admin = details.get('requested_by_admin', False)
        
        actor = "Coordinador solicitó" if requested_by_admin else "Solicitó"
        message = f"{actor} prórroga para '{archive_name}' hasta {requested_until}"
        if reason:
            message += f" (Motivo: {reason})"
        return message
    
    @staticmethod
    def _format_extension_decided(details: Dict[str, Any]) -> str:
        """Formato: 'Prórroga para [Documento] fue [aprobada/rechazada]'"""
        archive_name = details.get('archive_name', 'documento')
        decision = details.get('decision', 'decidida')
        granted_until = details.get('granted_until', '')
        condition_text = details.get('condition_text', '')
        
        decision_text = {
            'granted': 'aprobada',
            'rejected': 'rechazada',
            'cancelled': 'cancelada'
        }.get(decision, decision)
        
        message = f"Prórroga para '{archive_name}' fue {decision_text}"
        
        if decision == 'granted' and granted_until:
            message += f" hasta {granted_until}"
        
        if condition_text:
            message += f" (Condiciones: {condition_text})"
        
        return message
    
    @staticmethod
    def _format_event_registered(details: Dict[str, Any]) -> str:
        """Formato: 'Se registró al evento [Nombre] ([Tipo])'"""
        event_title = details.get('event_title', 'evento')
        event_type = details.get('event_type', '')
        
        message = f"Se registró al evento '{event_title}'"
        if event_type:
            type_text = {
                'interview': 'entrevista',
                'workshop': 'taller', 
                'conference': 'conferencia',
                'meeting': 'reunión'
            }.get(event_type, event_type)
            message += f" ({type_text})"
        
        return message
    
    @staticmethod
    def _format_appointment_assigned(details: Dict[str, Any]) -> str:
        """Formato: 'Se le asignó cita para [Evento] el [Fecha]'"""
        event_title = details.get('event_title', 'evento')
        appointment_datetime = details.get('appointment_datetime', 'fecha no especificada')
        
        # Formatear fecha si es posible
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(appointment_datetime.replace('Z', '+00:00'))
            formatted_date = dt.strftime('%d/%m/%Y a las %H:%M')
        except:
            formatted_date = appointment_datetime
        
        return f"Se le asignó cita para '{event_title}' el {formatted_date}"
    
    @staticmethod
    def _format_appointment_cancelled(details: Dict[str, Any]) -> str:
        """Formato: 'Cita para [Evento] fue cancelada'"""
        event_title = details.get('event_title', 'evento')
        reason = details.get('reason', '')
        cancelled_by_admin = details.get('cancelled_by_admin', False)
        
        actor = "fue cancelada por coordinador" if cancelled_by_admin else "fue cancelada"
        message = f"Cita para '{event_title}' {actor}"
        
        if reason and reason != 'Cancelada por el usuario':
            message += f" (Motivo: {reason})"
        
        return message
    
    @staticmethod
    def _format_control_number_assigned(details: Dict[str, Any]) -> str:
        """Formato: 'Se asignó número de control [Número] para [Programa]'"""
        if isinstance(details, dict):
            control_number = details.get('control_number', 'número no especificado')
            program = details.get('program', 'programa')
            return f"Se asignó número de control {control_number} para {program}"
        else:
            return f"Número de control asignado: {details}"
    
    @staticmethod
    def _format_archive_created(details: Dict[str, Any]) -> str:
        """Formato: 'Creó el archivo [Nombre] en el paso [Paso]'"""
        archive_name = details.get('archive_name', 'archivo desconocido')
        step_name = details.get('step_name', 'paso desconocido')
        return f"Creó el archivo '{archive_name}' en el paso {step_name}"
    
    @staticmethod
    def _format_archive_updated(details: Dict[str, Any]) -> str:
        """Formato: 'Modificó el archivo [Nombre] en el paso [Paso] - cambios: [lista]'"""
        archive_name = details.get('archive_name', 'archivo desconocido')
        step_name = details.get('step_name', 'paso desconocido')
        changes = details.get('changes', {})
        
        message = f"Modificó el archivo '{archive_name}' en el paso {step_name}"
        
        # Mostrar qué se cambió específicamente
        if changes and isinstance(changes, dict):
            change_list = []
            field_translations = {
                'name': 'nombre',
                'description': 'descripción',
                'coordinator_can_upload': 'permisos de coordinador',
                'allow_extensions': 'permisos de prórroga',
                'required': 'obligatoriedad'
            }
            
            for field, value in changes.items():
                if field in field_translations:
                    change_list.append(field_translations[field])
                else:
                    change_list.append(field)
            
            if change_list:
                if len(change_list) == 1:
                    message += f" (cambió: {change_list[0]})"
                else:
                    message += f" (cambió: {', '.join(change_list)})"
        
        return message
    
    @staticmethod
    def _format_archive_deleted(details: Dict[str, Any]) -> str:
        """Formato: 'Eliminó el archivo [Nombre]'"""
        archive_name = details.get('archive_name', 'archivo desconocido')
        archive_description = details.get('archive_description', '')
        force_used = details.get('force_used', False)
        
        message = f"Eliminó el archivo '{archive_name}'"
        
        if archive_description:
            message += f" ({archive_description})"
        
        if force_used:
            message += " (eliminación forzada)"
        
        return message
    
    @staticmethod
    def _format_template_uploaded(details: Dict[str, Any]) -> str:
        """Formato: 'Subió plantilla [archivo.ext] para el archivo [Nombre]'"""
        archive_name = details.get('archive_name', 'archivo desconocido')
        template_filename = details.get('template_filename', 'plantilla')
        was_replacement = details.get('was_replacement', False)
        
        action = "Reemplazó" if was_replacement else "Subió"
        return f"{action} la plantilla '{template_filename}' para el archivo '{archive_name}'"
    
    @staticmethod
    def _format_role_changed(details: Dict[str, Any]) -> str:
        """Formato: 'Rol cambiado de [Anterior] a [Nuevo]'"""
        old_role = details.get('old_role', 'rol anterior')
        new_role = details.get('new_role', 'rol nuevo')
        
        # Traducir roles a español
        role_translations = {
            'applicant': 'solicitante',
            'program_admin': 'coordinador de programa',
            'postgraduate_admin': 'administrador de posgrado',
            'document_reviewer': 'revisor de documentos',
            'social_service': 'servicio social'
        }
        
        old_role_es = role_translations.get(old_role, old_role)
        new_role_es = role_translations.get(new_role, new_role)
        
        return f"Rol cambiado de {old_role_es} a {new_role_es}"
    
    @staticmethod
    def _format_basic_info_updated(details: Dict[str, Any]) -> str:
        """Formato: 'Actualizó información personal: [campos]'"""
        if isinstance(details, dict) and 'changed_fields' in details:
            changed_fields = details['changed_fields']
            if isinstance(changed_fields, dict):
                field_names = list(changed_fields.keys())
                if len(field_names) == 1:
                    return f"Actualizó {field_names[0]}"
                elif len(field_names) <= 3:
                    return f"Actualizó {', '.join(field_names)}"
                else:
                    return f"Actualizó {len(field_names)} campos de información personal"
        
        return "Actualizó información personal"
    
    @staticmethod
    def _format_generic(action: str, details: Dict[str, Any]) -> str:
        """Formatter genérico para acciones no específicas."""
        if 'raw' in details:
            return str(details['raw'])
        
        # Intentar crear un mensaje legible basado en la acción
        action_translations = {
            'password_reset': 'Contraseña restablecida',
            'password_changed': 'Contraseña actualizada',
            'activated': 'Usuario activado',
            'deactivated': 'Usuario desactivado',
            'created': 'Usuario creado',
            'deleted': 'Usuario eliminado',
            'profile_completed': 'Perfil completado',
            'profile_updated': 'Perfil actualizado'
        }
        
        base_message = action_translations.get(action, f"Acción realizada: {action}")
        
        # Si hay detalles adicionales, intentar mostrar los más importantes
        if details and isinstance(details, dict):
            important_keys = ['reason', 'comment', 'message', 'description']
            for key in important_keys:
                if key in details and details[key]:
                    return f"{base_message} ({details[key]})"
        
        return base_message

    def format_history_entry(self, entry) -> str:
        """
        Formatea una entrada del historial para mostrar al usuario.
        
        Args:
            entry: Objeto UserHistory o diccionario con los datos de la entrada
            
        Returns:
            String con la descripción formateada de la entrada
        """
        # Si es un objeto UserHistory, extraer los datos necesarios
        if hasattr(entry, 'action'):
            action = entry.action
            details = entry.details if entry.details else {}
        else:
            # Si es un diccionario
            action = entry.get('action', '')
            details = entry.get('details', {})
        
        # Formatear los detalles usando el método estático
        formatted_description = self.format_details(action, details)
        
        return formatted_description

    @staticmethod  
    def format_history_entry_dict(entry_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formatea una entrada completa del historial devolviendo un diccionario.
        
        Args:
            entry_dict: Diccionario de la entrada del historial (resultado de to_dict())
            
        Returns:
            Diccionario con los detalles formateados
        """
        formatted_entry = entry_dict.copy()
        
        # Formatear los detalles
        formatted_entry['formatted_details'] = HistoryFormatter.format_details(
            action=entry_dict.get('action', ''),
            details=entry_dict.get('details', '')
        )
        
        # Mantener los detalles originales por si se necesitan
        formatted_entry['raw_details'] = entry_dict.get('details', '')
        
        # Formatear la fecha de manera más legible
        try:
            from datetime import datetime
            timestamp_str = entry_dict.get('timestamp', '')
            if timestamp_str:
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                formatted_entry['formatted_timestamp'] = dt.strftime('%d de %B de %Y a las %H:%M')
                formatted_entry['date_only'] = dt.strftime('%d/%m/%Y')
                formatted_entry['time_only'] = dt.strftime('%H:%M')
        except:
            formatted_entry['formatted_timestamp'] = entry_dict.get('timestamp', '')
            formatted_entry['date_only'] = ''
            formatted_entry['time_only'] = ''
        
        return formatted_entry
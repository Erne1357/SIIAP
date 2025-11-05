# app/routes/api/admin/history_api.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services.user_history_service import UserHistoryService
from app.services.history_retention_service import HistoryRetentionService
from app.utils.history_formatter import HistoryFormatter

api_admin_history = Blueprint('api_admin_history', __name__, url_prefix='/api/v1/admin/history')

@api_admin_history.route('/statistics', methods=['GET'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def get_history_statistics():
    """Obtiene estadísticas del historial de usuarios"""
    try:
        stats = HistoryRetentionService.get_retention_statistics()
        return jsonify({
            "ok": True,
            "statistics": stats
        }), 200
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@api_admin_history.route('/cleanup/preview', methods=['POST'])
@login_required
@roles_required('postgraduate_admin')  # Solo admin de posgrado puede hacer limpieza
def preview_cleanup():
    """Previsualiza qué registros se eliminarían en una limpieza"""
    data = request.get_json() or {}
    retention_config = data.get('retention_config')
    
    try:
        preview_stats = HistoryRetentionService.cleanup_old_history(
            dry_run=True,
            retention_config=retention_config
        )
        return jsonify({
            "ok": True,
            "preview": preview_stats,
            "message": "Previsualización completada - no se eliminó ningún registro"
        }), 200
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@api_admin_history.route('/cleanup/execute', methods=['POST'])
@login_required
@roles_required('postgraduate_admin')  # Solo admin de posgrado puede ejecutar limpieza
def execute_cleanup():
    """Ejecuta la limpieza del historial (OPERACIÓN DESTRUCTIVA)"""
    data = request.get_json() or {}
    retention_config = data.get('retention_config')
    confirm = data.get('confirm', False)
    
    if not confirm:
        return jsonify({
            "ok": False,
            "error": "Debe confirmar la operación con 'confirm': true"
        }), 400
    
    try:
        cleanup_stats = HistoryRetentionService.cleanup_old_history(
            dry_run=False,
            retention_config=retention_config
        )
        return jsonify({
            "ok": True,
            "cleanup_results": cleanup_stats,
            "message": f"Limpieza completada - {cleanup_stats['entries_deleted']} registros eliminados"
        }), 200
    except Exception as e:
        from app import db
        db.session.rollback()
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@api_admin_history.route('/actions/critical', methods=['GET'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def get_critical_actions():
    """Lista todas las acciones críticas definidas"""
    return jsonify({
        "ok": True,
        "critical_actions": list(UserHistoryService.CRITICAL_ACTIONS),
        "high_importance_actions": list(UserHistoryService.HIGH_IMPORTANCE_ACTIONS),
        "medium_importance_actions": list(UserHistoryService.MEDIUM_IMPORTANCE_ACTIONS),
        "action_descriptions": UserHistoryService.ACTIONS
    }), 200

@api_admin_history.route('/recent', methods=['GET'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def get_recent_history():
    """Obtiene historial reciente de todos los usuarios con formato legible"""
    limit = request.args.get('limit', 50, type=int)
    format_type = request.args.get('format', 'formatted')  # 'formatted' o 'raw'
    
    try:
        recent_entries = UserHistoryService.get_recent_activity(limit=limit)
        
        # Formatear las entradas si se solicita
        formatted_entries = []
        formatter = HistoryFormatter()
        
        for entry in recent_entries:
            entry_dict = entry.to_dict()
            
            # Agregar descripción formateada si se solicita
            if format_type == 'formatted':
                entry_dict['formatted_description'] = formatter.format_history_entry(entry)
            
            formatted_entries.append(entry_dict)
        
        return jsonify({
            "ok": True,
            "entries": formatted_entries,
            "count": len(recent_entries),
            "format_type": format_type
        }), 200
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@api_admin_history.route('/retention-policies', methods=['GET'])
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def get_retention_policies():
    """Obtiene las políticas de retención para cada tipo de acción"""
    try:
        policies = {}
        for action in UserHistoryService.ACTIONS.keys():
            policies[action] = UserHistoryService.get_retention_policy_for_action(action)
        
        return jsonify({
            "ok": True,
            "policies": policies,
            "default_config": HistoryRetentionService.DEFAULT_RETENTION
        }), 200
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500
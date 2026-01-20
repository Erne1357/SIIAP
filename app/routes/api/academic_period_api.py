# app/routes/api/academic_period_api.py
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.utils.auth import roles_required
from app.services import academic_period_service as svc
import logging

api_academic_periods = Blueprint(
    'api_academic_periods',
    __name__,
    url_prefix='/api/v1/academic-periods'
)

@api_academic_periods.route('', methods=['GET'])
@login_required
@roles_required('postgraduate_admin')
def api_list_periods():
    """Lista todos los periodos académicos."""
    include_completed = request.args.get('include_completed', 'true').lower() == 'true'
    periods = svc.list_academic_periods(include_completed=include_completed)
    data = [p.to_dict() for p in periods]

    return jsonify({
        "data": data,
        "error": None,
        "meta": {"count": len(data)}
    }), 200

@api_academic_periods.route('', methods=['POST'])
@login_required
@roles_required('postgraduate_admin')
def api_create_period():
    """Crea un nuevo periodo académico."""
    data = request.get_json()

    if not data:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Datos inválidos."}],
            "error": {"code": "INVALID_DATA", "message": "Datos inválidos"},
            "meta": {}
        }), 400

    # Validar campos requeridos
    required_fields = ['code', 'name', 'start_date', 'end_date',
                       'admission_start_date', 'admission_end_date']
    missing = [f for f in required_fields if not data.get(f)]

    if missing:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": f"Faltan campos requeridos: {', '.join(missing)}"}],
            "error": {"code": "MISSING_FIELDS", "message": f"Campos requeridos: {', '.join(missing)}"},
            "meta": {}
        }), 400

    try:
        period = svc.create_academic_period(data, created_by=current_user.id)

        return jsonify({
            "data": period.to_dict(),
            "flash": [{"level": "success", "message": f"Periodo {period.code} creado correctamente."}],
            "error": None,
            "meta": {}
        }), 201

    except svc.InvalidPeriodCode as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "INVALID_CODE", "message": str(e)},
            "meta": {}
        }), 400

    except svc.DuplicatePeriodCode as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": str(e)}],
            "error": {"code": "DUPLICATE_CODE", "message": str(e)},
            "meta": {}
        }), 409

    except svc.InvalidDateRange as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "INVALID_DATE_RANGE", "message": str(e)},
            "meta": {}
        }), 400

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error al crear periodo académico: {e}")
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al crear el periodo."}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_academic_periods.get('/active')
@login_required
def api_get_active_period():
    """Obtiene el periodo académico activo actual."""
    period = svc.get_active_period()

    if not period:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": "No hay un periodo activo actualmente"},
            "meta": {}
        }), 404

    return jsonify({
        "data": period.to_dict(),
        "error": None,
        "meta": {}
    }), 200


@api_academic_periods.get('/<int:period_id>')
@login_required
@roles_required('postgraduate_admin')
def api_get_period(period_id):
    """Obtiene un periodo académico por ID."""
    try:
        period = svc.get_academic_period_by_id(period_id)
    except svc.AcademicPeriodNotFound:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": "Periodo académico no encontrado"},
            "meta": {}
        }), 404

    return jsonify({
        "data": period.to_dict(),
        "error": None,
        "meta": {}
    }), 200



@api_academic_periods.patch('/<int:period_id>')
@login_required
@roles_required('postgraduate_admin')
def api_update_period(period_id):
    """Actualiza un periodo académico existente."""
    data = request.get_json()

    if not data:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Datos inválidos."}],
            "error": {"code": "INVALID_DATA", "message": "Datos inválidos"},
            "meta": {}
        }), 400

    try:
        period = svc.update_academic_period(period_id, data)

        return jsonify({
            "data": period.to_dict(),
            "flash": [{"level": "success", "message": "Periodo actualizado correctamente."}],
            "error": None,
            "meta": {}
        }), 200

    except svc.AcademicPeriodNotFound:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Periodo no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Periodo académico no encontrado"},
            "meta": {}
        }), 404

    except svc.InvalidPeriodCode as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "INVALID_CODE", "message": str(e)},
            "meta": {}
        }), 400

    except svc.DuplicatePeriodCode as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": str(e)}],
            "error": {"code": "DUPLICATE_CODE", "message": str(e)},
            "meta": {}
        }), 409

    except svc.InvalidDateRange as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "INVALID_DATE_RANGE", "message": str(e)},
            "meta": {}
        }), 400

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error al actualizar periodo: {e}")
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al actualizar el periodo."}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_academic_periods.post('/<int:period_id>/activate')
@login_required
@roles_required('postgraduate_admin')
def api_activate_period(period_id):
    """Activa un periodo académico (desactiva automáticamente el anterior)."""
    try:
        period = svc.activate_period(period_id)

        return jsonify({
            "data": period.to_dict(),
            "flash": [{"level": "success", "message": f"Periodo {period.code} activado. Los demás periodos han sido desactivados."}],
            "error": None,
            "meta": {}
        }), 200

    except svc.AcademicPeriodNotFound:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Periodo no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Periodo académico no encontrado"},
            "meta": {}
        }), 404

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error al activar periodo: {e}")
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al activar el periodo."}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_academic_periods.post('/<int:period_id>/deactivate')
@login_required
@roles_required('postgraduate_admin')
def api_deactivate_period(period_id):
    """Desactiva un periodo académico."""
    try:
        period = svc.deactivate_period(period_id)

        return jsonify({
            "data": period.to_dict(),
            "flash": [{"level": "success", "message": f"Periodo {period.code} desactivado."}],
            "error": None,
            "meta": {}
        }), 200

    except svc.AcademicPeriodNotFound:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Periodo no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Periodo académico no encontrado"},
            "meta": {}
        }), 404

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error al desactivar periodo: {e}")
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al desactivar el periodo."}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_academic_periods.delete('/<int:period_id>')
@login_required
@roles_required('postgraduate_admin')
def api_delete_period(period_id):
    """Elimina un periodo académico."""
    try:
        svc.delete_academic_period(period_id)

        return jsonify({
            "data": None,
            "flash": [{"level": "success", "message": "Periodo eliminado correctamente."}],
            "error": None,
            "meta": {}
        }), 200

    except svc.AcademicPeriodNotFound:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Periodo no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Periodo académico no encontrado"},
            "meta": {}
        }), 404

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error al eliminar periodo: {e}")
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al eliminar el periodo."}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500

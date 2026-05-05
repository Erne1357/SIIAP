# app/routes/api/student_record_api.py
"""
REST endpoints for the Student Record (Expediente Completo).
"""
from flask import Blueprint, jsonify, request, send_file
from flask_login import login_required, current_user
from io import BytesIO

from app import db
from app.services import student_record_service as svc
from app.utils.permissions import permission_required


api_student_record = Blueprint(
    'api_student_record',
    __name__,
    url_prefix='/api/v1/students',
)


@api_student_record.get('/<int:user_id>/record')
@login_required
@permission_required('students.api.view_record')
def get_record(user_id):
    try:
        data = svc.get_full_record(user_id, requester=current_user)
        return jsonify({"data": data, "error": None, "meta": {}}), 200
    except svc.AccessDenied as e:
        return jsonify({
            "data": None,
            "error": {"code": "FORBIDDEN", "message": str(e)},
            "meta": {}
        }), 403
    except svc.StudentNotFound as e:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404
    except Exception as e:
        return jsonify({
            "data": None,
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_student_record.patch('/<int:user_id>/personal-info')
@login_required
def patch_personal_info(user_id):
    if not current_user.has_permission('students.api.edit_personal_info'):
        return jsonify({
            "data": None,
            "error": {"code": "FORBIDDEN", "message": "Sin permiso"},
            "meta": {}
        }), 403

    payload = request.get_json(silent=True) or {}
    try:
        user = svc.update_personal_info(user_id, current_user.id, payload)
        return jsonify({
            "data": svc._user_dict(user),
            "flash": [{"level": "success", "message": "Información actualizada"}],
            "error": None,
            "meta": {}
        }), 200
    except svc.AccessDenied as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "FORBIDDEN", "message": str(e)},
            "meta": {}
        }), 403
    except svc.StudentNotFound as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Error al actualizar"}],
            "error": {"code": "SERVER_ERROR", "message": str(e)},
            "meta": {}
        }), 500


@api_student_record.get('/<int:user_id>/record/pdf')
@login_required
@permission_required('students.api.export_record_pdf')
def export_record_pdf(user_id):
    """Generates a PDF of the student record using WeasyPrint."""
    try:
        data = svc.get_full_record(user_id, requester=current_user)
    except svc.AccessDenied as e:
        return jsonify({
            "data": None,
            "error": {"code": "FORBIDDEN", "message": str(e)},
            "meta": {}
        }), 403
    except svc.StudentNotFound as e:
        return jsonify({
            "data": None,
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404

    try:
        from flask import render_template
        from weasyprint import HTML
        html = render_template('coordinator/student_record/_pdf.html', record=data)
        pdf_bytes = HTML(string=html).write_pdf()
        full_name = (
            f"{data['user']['first_name']}_{data['user']['last_name']}"
        ).replace(' ', '_')
        filename = f"expediente_{full_name}_{user_id}.pdf"
        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({
            "data": None,
            "error": {"code": "SERVER_ERROR", "message": f"Error generando PDF: {e}"},
            "meta": {}
        }), 500

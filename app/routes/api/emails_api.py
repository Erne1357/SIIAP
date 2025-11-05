from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.utils.auth import roles_required
from app.services.email_service import EmailService
from app.utils.ms_graph import is_connected, acquire_token_silent, read_account_info
from app import db

api_emails = Blueprint('api_emails', __name__, url_prefix='/api/v1/emails')


@api_emails.get('/status')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def email_status():
    """Verifica el estado de la conexión con Microsoft"""
    connected = is_connected()
    account = read_account_info()
    stats = EmailService.get_queue_stats()
    
    return jsonify({
        'data': {
            'connected': connected,
            'account': account,
            'stats': stats
        }
    }), 200


@api_emails.get('/queue/stats')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def queue_stats():
    """Obtiene estadísticas de la cola de correos"""
    stats = EmailService.get_queue_stats()
    
    return jsonify({
        'data': stats
    }), 200


@api_emails.get('/queue/pending')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def queue_pending():
    """Lista correos pendientes"""
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    
    result = EmailService.get_pending_emails(limit, offset)
    
    return jsonify({
        'data': result,
        'meta': {
            'limit': limit,
            'offset': offset
        }
    }), 200


@api_emails.post('/queue/process')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def process_queue():
    """Procesa la cola de correos pendientes manualmente"""
    limit = min(int(request.args.get('limit', 50)), 100)
    
    result = EmailService.process_queue(limit)
    
    if 'error' in result:
        return jsonify({
            'data': None,
            'flash': [{
                'level': 'error',
                'message': result['error']
            }]
        }), 400
    
    return jsonify({
        'data': result,
        'flash': [{
            'level': 'success',
            'message': f"{result['sent']} correos enviados exitosamente"
        }]
    }), 200


@api_emails.post('/queue/retry-failed')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def retry_failed():
    """Reintenta enviar correos fallidos"""
    result = EmailService.retry_failed()
    
    if 'error' in result:
        return jsonify({
            'data': None,
            'flash': [{
                'level': 'error',
                'message': result['error']
            }]
        }), 400
    
    return jsonify({
        'data': result,
        'flash': [{
            'level': 'success',
            'message': f"{result['sent']} correos reenviados"
        }]
    }), 200


@api_emails.post('/test')
@login_required
@roles_required('postgraduate_admin')
def send_test_email():
    """Envía un correo de prueba al usuario actual"""
    from flask_login import current_user
    from app.services.email_templates import EmailTemplates
    from flask import url_for
    
    if not is_connected():
        return jsonify({
            'data': None,
            'flash': [{
                'level': 'error',
                'message': 'No hay conexión activa con Microsoft'
            }]
        }), 400
    
    try:
        dashboard_url = url_for('pages_user.dashboard', _external=True)
        subject = "✅ Correo de prueba - SIIAP"
        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>🎉 ¡Correo de Prueba Exitoso!</h2>
            <p>Hola <strong>{current_user.first_name} {current_user.last_name}</strong>,</p>
            <p>Este es un correo de prueba del sistema SIIAP.</p>
            <p>Si recibes este mensaje, significa que la configuración de correos está funcionando correctamente.</p>
            <hr>
            <p style="color: #666; font-size: 14px;">
                Instituto Tecnológico de Ciudad Juárez<br>
                Sistema Integral de Información Académica de Posgrado
            </p>
        </body>
        </html>
        """
        
        EmailService.queue_email(current_user.id, subject, html)
        db.session.commit()
        
        return jsonify({
            'data': {'sent': True},
            'flash': [{
                'level': 'success',
                'message': f'Correo de prueba enviado a {current_user.email}'
            }]
        }), 200
        
    except Exception as e:
        return jsonify({
            'data': None,
            'flash': [{
                'level': 'error',
                'message': f'Error al enviar correo de prueba: {str(e)}'
            }]
        }), 500
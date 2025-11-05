from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required
from app.utils.auth import roles_required
from app.utils.ms_graph import build_auth_url, process_auth_code, clear_account_and_cache, read_account_info
from app.services.email_service import EmailService

pages_emails = Blueprint('pages_emails', __name__)


@pages_emails.route('/admin/emails')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def email_config():
    """Página de configuración de correos"""
    account = read_account_info()
    stats = EmailService.get_queue_stats()
    
    return render_template('admin/settings/emails.html', 
                         ms_account=account,
                         stats=stats)


@pages_emails.route('/admin/emails/login')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def ms_login():
    """Inicia el flujo de autenticación con Microsoft"""
    state = "email_config"
    return redirect(build_auth_url(state))


@pages_emails.route('/admin/emails/callback')
def ms_callback():
    """Callback de Microsoft después de autenticación"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f"Error de autenticación: {error}", 400
    
    if not code:
        return "Falta código de autorización", 400
    
    result = process_auth_code(code)
    
    if result.get('error'):
        return f"Error MSAL: {result['error_description']}", 400
    
    # Procesar cola después de conectar
    EmailService.process_queue()
    
    return redirect(url_for('pages_emails.email_config'))


@pages_emails.post('/admin/emails/logout')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def ms_logout():
    """Cierra sesión de Microsoft"""
    clear_account_and_cache()
    return jsonify({'ok': True})


@pages_emails.post('/admin/emails/process-queue')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def process_email_queue():
    """Procesa la cola de correos manualmente"""
    try:
        result = EmailService.process_queue()
        return jsonify({
            'ok': True,
            'result': result
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@pages_emails.get('/admin/emails/queue')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def get_email_queue():
    """Obtiene el estado actual de la cola de correos"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        offset = (page - 1) * per_page
        result = EmailService.get_pending_emails(limit=per_page, offset=offset)
        
        return jsonify({
            'ok': True,
            'emails': result['items'],
            'total': result['total'],
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@pages_emails.post('/admin/emails/retry-failed')
@login_required
@roles_required('postgraduate_admin', 'program_admin')
def retry_failed_emails():
    """Reintenta enviar correos fallidos"""
    try:
        result = EmailService.retry_failed()
        return jsonify({
            'ok': True,
            'result': result
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500
# app/utils/csrf.py
import secrets, hmac
from flask import session, request, abort

CSRF_SESSION_KEY = "_csrf_token"
CSRF_HEADER = "X-CSRFToken"

def generate_csrf_token(force_new=False) -> str:
    """Genera o retorna el token CSRF de la sesión.
    
    Args:
        force_new: Si es True, fuerza la creación de un nuevo token
    """
    if force_new:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
        return token
    
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token

def validate_csrf_for_api():
    # Sólo protege métodos que modifican estado
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        # Valida sólo en API (prefijo /api/)
        if request.path.startswith("/api/"):
            # Excepciones: endpoints que no requieren CSRF
            # (login y register están protegidos por credenciales)
            csrf_exempt_paths = [
                "/api/v1/auth/login",
                "/api/v1/auth/register",
            ]
            
            if request.path in csrf_exempt_paths:
                return
            
            sent = request.headers.get(CSRF_HEADER, "")
            saved = session.get(CSRF_SESSION_KEY, "")
            
            # Si no hay token en sesión, generarlo para la próxima petición
            if not saved:
                generate_csrf_token()
                abort(400, description="Sesión expirada. Por favor, recarga la página.")
            
            if not sent:
                abort(400, description="Token CSRF no enviado en la petición")
            
            if not hmac.compare_digest(sent, saved):
                abort(400, description="Token CSRF inválido. Por favor, recarga la página.")

# app/utils/csrf.py
"""
CSRF protection: Flask-WTF `CSRFProtect` over every mutating request.

The previous hand-rolled guard only validated paths under `/api/`, so any
mutating page route (e.g. `/programs/<id>/inscription`) shipped unprotected
in silence. CSRFProtect inverts the failure mode: a new mutating route is
protected by default and an unprotected one is visible as an explicit
`csrf.exempt`.

The browser sends the signed token in the `X-CSRFToken` header (read from
`<meta name="csrf-token">`) or in a `csrf_token` form field.
"""
from flask import g, session
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf

csrf = CSRFProtect()

# Flask-WTF keeps the raw token in session[WTF_CSRF_FIELD_NAME]; the page
# receives a signed copy of it.
CSRF_SESSION_KEY = "csrf_token"
CSRF_HEADER = "X-CSRFToken"

# Credentials are the protection on these: there is no session to ride yet.
CSRF_EXEMPT_VIEWS = (
    "app.routes.api.auth_api.api_login",
)

# Flask-WTF's English reasons → the Spanish message shown to the user.
_REASONS_ES = {
    "The CSRF token is missing.": "Token CSRF no enviado en la petición",
    "The CSRF session token is missing.": "Sesión expirada. Por favor, recarga la página.",
    "The CSRF token has expired.": "Sesión expirada. Por favor, recarga la página.",
    "The CSRF token is invalid.": "Token CSRF inválido. Por favor, recarga la página.",
    "The CSRF tokens do not match.": "Token CSRF inválido. Por favor, recarga la página.",
    "The referrer header is missing.": "Solicitud rechazada: falta el origen de la petición. Recarga la página.",
    "The referrer does not match the host.": "Solicitud rechazada: el origen de la petición no coincide.",
}
_DEFAULT_REASON_ES = "Token CSRF inválido. Por favor, recarga la página."


def init_csrf(app) -> None:
    """Enable CSRFProtect on `app` with the project's settings."""
    # Tokens live as long as the session; inactivity expiry (15 min) already
    # ends the session. The default 1 h limit broke pages left open.
    app.config.setdefault("WTF_CSRF_TIME_LIMIT", None)
    app.config.setdefault("WTF_CSRF_FIELD_NAME", CSRF_SESSION_KEY)
    csrf.init_app(app)
    for view in CSRF_EXEMPT_VIEWS:
        csrf.exempt(view)


def generate_csrf_token(force_new: bool = False) -> str:
    """
    Return the signed CSRF token for the current session.

    Args:
        force_new: drop the session's token first, so the next page gets a
            fresh one (login and the login page rotate it).
    """
    # Flask-WTF keeps an existing session value even when it is empty, which
    # would sign '' and fail every later validation.
    if force_new or not session.get(CSRF_SESSION_KEY):
        session.pop(CSRF_SESSION_KEY, None)
        g.pop(CSRF_SESSION_KEY, None)
    return generate_csrf()


def csrf_error_message(error: CSRFError) -> str:
    """Spanish message for a CSRFError raised by Flask-WTF."""
    return _REASONS_ES.get(error.description, _DEFAULT_REASON_ES)

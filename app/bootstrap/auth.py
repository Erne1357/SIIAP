"""Flask-Login wiring: manager setup, unauthorized handler and user loader."""
from datetime import timedelta

from flask import flash, jsonify, redirect, request, url_for

from app.utils.htmx import hx_redirect, wants_html_fragment


def register_login_manager(app, login_manager):
    # Login manager
    login_manager.init_app(app)
    login_manager.login_view = 'pages_auth.login_page'
    login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
    login_manager.login_message_category = "warning"

    @login_manager.unauthorized_handler
    def unauthorized():
        if wants_html_fragment():
            # login_required on a fragment route: htmx must navigate, not follow a 302.
            flash(login_manager.login_message, login_manager.login_message_category)
            return hx_redirect(url_for(login_manager.login_view), status=401)
        if request.path.startswith('/api/'):
            return jsonify({
                "data": None,
                "error": {"code": "UNAUTHORIZED", "message": "No autenticado"},
                "meta": {}
            }), 401
        if request.endpoint != 'pages_auth.login_page':
            flash(login_manager.login_message, login_manager.login_message_category)
        return redirect(url_for(login_manager.login_view))

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        """
        Resolve the session cookie to a user.

        A malformed identifier resolves to "anonymous", never to an exception.
        int(user_id) on a cookie whose _user_id is not an integer (a stale
        cookie, or one minted on either side of the pending UUID migration)
        raised straight out of the login manager on EVERY request — including
        /login and /logout — so the victim could not clear the bad session from
        inside the app at all; the only way out was deleting the cookie by hand.

        Returns None for a deactivated account so that the very next request
        from an existing cookie is anonymous. Without this, deactivating a
        compromised account changed nothing for whoever already held a session:
        the before_request handler rewrote last_activity on every request, so
        the 15-minute idle window never closed and the cookie stayed valid
        indefinitely.
        """
        try:
            pk = int(user_id)
        except (TypeError, ValueError):
            return None
        user = User.query.get(pk)
        if user is None or not user.is_active:
            return None
        return user

    app.permanent_session_lifetime = timedelta(minutes=17)

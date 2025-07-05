from functools import wraps
from flask import abort
from flask_login import current_user

def roles_required(*role_names):
    """
    Abort 403 si el usuario no tiene **todos** los roles indicados.
    Uso:
        @login_required
        @roles_required('applicant')
        def vista():
            ...
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if (not current_user.is_authenticated or
                not current_user.has_role(*role_names)):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator

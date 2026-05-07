"""
Decoradores y utilidades para el sistema de permisos granulares de SIIAP.

Uso en rutas API:

    @permission_required('acceptance.api.list_applicants')
    def list_applicants(program_id):
        ...

    # Con scope de programa extraído del URL:
    @permission_required('acceptance.api.list_applicants', program_id_kwarg='program_id')
    def list_applicants(program_id):
        ...

    # Si basta con tener al menos uno de varios permisos:
    @any_permission_required('acceptance.api.list_applicants', 'acceptance.api.view_stats')
    def vista():
        ...
"""

from functools import wraps
from flask import abort, request, jsonify
from flask_login import current_user


def _abort_403():
    """
    Devuelve 403 en JSON para rutas API o AJAX,
    y deja que el error handler global maneje el resto (redirect + flash).
    """
    if (request.path.startswith('/api/') or
            request.is_json or
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No tienes permiso para realizar esta acción."}],
            "error": {"code": "FORBIDDEN", "message": "No tienes permiso para realizar esta acción."},
            "meta": {}
        }), 403
    abort(403)


def permission_required(codename, program_id_kwarg=None):
    """
    Decorador que protege una vista exigiendo un permiso específico.

    Args:
        codename (str): Codename del permiso requerido. Ej: 'acceptance.api.upload_doc'
        program_id_kwarg (str | None): Nombre del argumento de URL que contiene el
            program_id. Si se indica, el permiso se evalúa con ese scope de programa.
            Ej: program_id_kwarg='program_id' extrae kwargs['program_id'].

    Comportamiento:
        - 401 si el usuario no está autenticado.
        - 403 si no tiene el permiso (JSON para /api/, redirect para páginas).
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            program_id = None
            if program_id_kwarg:
                try:
                    program_id = int(kwargs.get(program_id_kwarg))
                except (TypeError, ValueError):
                    program_id = None

            if not current_user.has_permission(codename, program_id=program_id):
                return _abort_403()

            return view(*args, **kwargs)
        return wrapped
    return decorator


def any_permission_required(*codenames):
    """
    Decorador que permite el acceso si el usuario tiene AL MENOS UNO
    de los permisos indicados.

    Args:
        *codenames: Uno o más codenames de permiso.

    Ejemplo:
        @any_permission_required('admin_review.api.decide', 'admin_review.api.list_submissions')
        def vista():
            ...
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            if not any(current_user.has_permission(c) for c in codenames):
                return _abort_403()

            return view(*args, **kwargs)
        return wrapped
    return decorator

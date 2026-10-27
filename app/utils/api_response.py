"""
Builders for the standard JSON envelope of every /api endpoint.

    success: {"data": ..., "error": null, "meta": {...}}
    failure: {"data": null, "flash": [...], "error": {"code", "message"[, "fields"]}, "meta": {}}

Routes return `api_ok(...)` / `api_error(...)` instead of hand-written
`jsonify({...})` dictionaries. An unexpected exception goes through
`api_server_error(exc)`, which logs the traceback and returns a generic
Spanish message: `str(e)` must never reach the client, it leaks table names,
file paths and SQL.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from flask import jsonify

logger = logging.getLogger(__name__)

SERVER_ERROR_MESSAGE = 'Ocurrió un error interno. Intenta de nuevo más tarde.'


def api_ok(data: Any = None, *, status: int = 200, meta: Optional[dict] = None,
           flash: Optional[list] = None):
    """Success envelope. `flash` is a list of {"level", "message"} dicts."""
    body = {'data': data, 'error': None, 'meta': meta or {}}
    if flash:
        body['flash'] = flash
    return jsonify(body), status


def api_error(code: str, message: str, *, status: int = 400, level: str = 'warning',
              fields: Optional[dict] = None):
    """Failure envelope with the message also queued as a flash for the UI."""
    error = {'code': code, 'message': message}
    if fields:
        error['fields'] = fields
    return jsonify({
        'data': None,
        'flash': [{'level': level, 'message': message}],
        'error': error,
        'meta': {},
    }), status


def api_not_found(message: str = 'Recurso no encontrado.'):
    return api_error('NOT_FOUND', message, status=404)


CONFLICT_MESSAGE = ('La operación entra en conflicto con datos existentes '
                    '(registro duplicado o todavía en uso).')


def api_server_error(exc: Optional[BaseException] = None, *,
                     message: str = SERVER_ERROR_MESSAGE, context: str = ''):
    """
    Answer the catch-all `except Exception as e` of a route.

    Not every exception that reaches it is a server fault, so it is
    classified first:
    - DomainError -> its own envelope (status, code, Spanish message);
    - ValueError -> 400 BUSINESS_ERROR with its message: services in this
      codebase raise ValueError with Spanish, user-facing text;
    - IntegrityError -> rollback + 409 CONFLICT with a generic Spanish
      message (the raw text names tables and constraints);
    - anything else -> traceback to the log, generic 500.

    The session is always rolled back first: routes no longer do it
    themselves, and a failed flush leaves it unusable for the rest of the
    request (PendingRollbackError on the next query).
    """
    from sqlalchemy.exc import IntegrityError

    from app.services.errors import DomainError

    if exc is not None:
        _rollback_quietly()
    if isinstance(exc, DomainError):
        return domain_error_response(exc)
    if isinstance(exc, IntegrityError):
        logger.warning('Integrity conflict%s: %s', f' in {context}' if context else '', exc.orig)
        return api_error('CONFLICT', CONFLICT_MESSAGE, status=409)
    if isinstance(exc, ValueError) and str(exc):
        return api_error('BUSINESS_ERROR', str(exc), status=400)
    if exc is not None:
        logger.error('Unhandled error%s', f' in {context}' if context else '',
                     exc_info=(type(exc), exc, exc.__traceback__))
    return api_error('SERVER_ERROR', message, status=500, level='danger')


def _rollback_quietly() -> None:
    try:
        from app import db
        db.session.rollback()
    except Exception:  # noqa: BLE001 - a broken session must not mask the original error
        logger.exception('Rollback failed while handling an error response')


def domain_error_response(err):
    """Envelope for a DomainError (see app/services/errors.py)."""
    return api_error(err.code, err.message or str(err), status=err.status_code,
                     level=err.level, fields=err.fields)

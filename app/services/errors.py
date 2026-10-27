"""
Base classes for business (domain) errors raised by services.

A service raises a DomainError subclass with a Spanish, user-facing message;
the app-level error handler (app/__init__.py) turns it into the standard
envelope, so a route does not need its own try/except for business rules:

    {"data": null,
     "flash": [{"level": "warning", "message": "..."}],
     "error": {"code": "BUSINESS_ERROR", "message": "...", "fields": {...}},
     "meta": {}}

Existing per-service bases (AcceptanceError, DeferralError, ...) inherit from
these, so routes that still catch them keep working unchanged.
"""
from __future__ import annotations

from typing import Optional


class DomainError(Exception):
    """A business rule refused the operation (HTTP 400)."""

    status_code = 400
    code = 'BUSINESS_ERROR'
    level = 'warning'

    def __init__(self, message: str = '', *, fields: Optional[dict] = None,
                 code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.fields = fields or None
        if code:
            self.code = code


class NotFoundError(DomainError):
    """The target does not exist, or the caller may not know it exists (404)."""

    status_code = 404
    code = 'NOT_FOUND'


class ConflictError(DomainError):
    """The operation clashes with the current state of the data (409)."""

    status_code = 409
    code = 'CONFLICT'


class ValidationFailed(DomainError):
    """The request payload is malformed or incomplete (400)."""

    code = 'VALIDATION_ERROR'

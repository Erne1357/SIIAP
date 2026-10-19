"""Request models for /api/v1/deliberation (shape and type checks only)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, field_validator

_TRUE_STRINGS = ('true', '1', 'yes', 'on')


class AcceptApplicantIn(BaseModel):
    """JSON or multipart body of POST /user/<uuid>/program/<id>/accept."""

    notes: Optional[str] = None
    is_conditional: bool = False

    @field_validator('is_conditional', mode='before')
    @classmethod
    def _lenient_bool(cls, value: Any):
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip().lower() in _TRUE_STRINGS
        return bool(value)


class RejectApplicantIn(BaseModel):
    """Body of POST /user/<uuid>/program/<id>/reject."""

    rejection_type: Optional[str] = 'full'
    notes: Optional[str] = None
    #: JSON {archive_id, archive_name, notes} (archive_id = public UUID).
    correction_required: Optional[Any] = None


class ResetApplicantIn(BaseModel):
    """Body of POST /user/<uuid>/program/<id>/reset."""

    reason: Optional[str] = None


class ForceResetIn(BaseModel):
    """Body of POST /user/<uuid>/program/<id>/force-reset."""

    reason: Optional[str] = 'Reinicio administrativo'

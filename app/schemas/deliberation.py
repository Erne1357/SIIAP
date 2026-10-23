"""Request models for /api/v1/deliberation (shape and type checks only)."""
from __future__ import annotations

import json
from datetime import date
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator

_TRUE_STRINGS = ('true', '1', 'yes', 'on')


class AdmissionConditionIn(BaseModel):
    """One condition of a conditional acceptance (phase 6C)."""

    description: str = Field(min_length=1, max_length=2000)
    #: archive_key of the conclusion requirement that fulfils it (optional).
    archive_key: Optional[str] = None
    due_date: Optional[date] = None

    @field_validator('description', mode='before')
    @classmethod
    def _strip(cls, value: Any):
        return value.strip() if isinstance(value, str) else value

    @field_validator('archive_key', 'due_date', mode='before')
    @classmethod
    def _blank_is_none(cls, value: Any):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class AcceptApplicantIn(BaseModel):
    """JSON or multipart body of POST /user/<uuid>/program/<id>/accept."""

    notes: Optional[str] = None
    is_conditional: bool = False
    #: Only used when `is_conditional`. Multipart sends it as a JSON string.
    conditions: List[AdmissionConditionIn] = Field(default_factory=list)

    @field_validator('conditions', mode='before')
    @classmethod
    def _conditions_from_json(cls, value: Any):
        if value is None or value == '':
            return []
        if isinstance(value, str):
            try:
                return json.loads(value)
            except ValueError:
                raise ValueError('Las condiciones deben ser una lista JSON.')
        return value

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

"""Request models for /api/v1/permanence (shape and type checks only).

The "missing field" checks that carry their own error code (MISSING_FIELD, ...)
stay in the routes; business rules stay in `permanence_service`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator

_TRUE_STRINGS = ('true', '1', 'yes', 'on')


def _blank_to_none(value: Any):
    """Strip strings; blank means "not given"."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class _Base(BaseModel):
    @field_validator('*', mode='before')
    @classmethod
    def _normalise(cls, value: Any):
        return _blank_to_none(value)


class ConfirmEnrollmentIn(_Base):
    """JSON or form body of POST /user-program/<id>/confirm."""

    academic_period_id: Optional[int] = None
    notes: Optional[str] = None
    force: bool = False

    @field_validator('force', mode='before')
    @classmethod
    def _lenient_bool(cls, value: Any):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in _TRUE_STRINGS


class EnrollmentStatusIn(_Base):
    """Body of PATCH /semester-enrollment/<id>/status."""

    status: Optional[str] = None
    notes: Optional[str] = None


class CreateDeadlineIn(_Base):
    """Body of POST /program/<id>/deadlines."""

    #: Public UUID of the Archive.
    archive_id: Optional[str] = None
    label: Optional[str] = None
    sequence: int = 1
    academic_period_id: Optional[int] = None
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None

    @field_validator('sequence', mode='before')
    @classmethod
    def _default_sequence(cls, value: Any):
        return 1 if value in (None, '') else value


class ToggleDeadlineIn(BaseModel):
    """Body of PATCH /deadlines/<id>/toggle. Check `'is_open' in model_fields_set`."""

    is_open: Optional[bool] = None


class UpdateDeadlineIn(BaseModel):
    """Body of PATCH /deadlines/<id>."""

    label: Optional[str] = None
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    is_open: Optional[bool] = None

    @field_validator('opens_at', 'closes_at', mode='before')
    @classmethod
    def _lenient_datetime(cls, value: Any):
        # Accepts 'YYYY-MM-DD' (date input) or an ISO string; anything that
        # does not parse counts as "not given".
        if value in (None, ''):
            return None
        try:
            if 'T' in value:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            return datetime.strptime(value, '%Y-%m-%d')
        except (TypeError, ValueError):
            return None


class ReviewDocumentIn(_Base):
    """Body of POST /submissions/<uuid>/review."""

    status: Optional[str] = None
    notes: Optional[str] = None


class LeaveDecisionIn(_Base):
    """Body of POST /submissions/<uuid>/leave-request."""

    approve: Optional[bool] = None
    notes: Optional[str] = None


class MonthlyDeadlinesIn(BaseModel):
    """Body of POST /program/<id>/deadlines/conacyt-monthly."""

    academic_period_id: Optional[int] = None

    @field_validator('academic_period_id', mode='before')
    @classmethod
    def _blank(cls, value: Any):
        return None if value == '' else value


class ConacytScholarshipIn(BaseModel):
    """Body of PATCH /user-program/<id>/conacyt-scholarship (omit `value` to toggle)."""

    value: Optional[bool] = None


class TransitionExecuteIn(BaseModel):
    """Body of POST /transition/execute."""

    source_period_id: Optional[int] = None
    target_period_id: Optional[int] = None
    program_id: Optional[int] = None

    @field_validator('*', mode='before')
    @classmethod
    def _blank(cls, value: Any):
        return None if value == '' else value

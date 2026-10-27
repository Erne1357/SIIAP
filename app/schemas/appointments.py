"""Request models for /api/v1/appointments (shape and type checks only).

Business rules (slot availability, status transitions) stay in
`AppointmentsService`.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class AssignIn(BaseModel):
    """Body of POST /api/v1/appointments."""

    event_id: int
    slot_id: int
    #: Public UUID of the applicant (staff only; applicants book for themselves).
    applicant_id: Optional[str] = None
    notes: Optional[str] = None


class ChangeRequestIn(BaseModel):
    """Body of POST /<id>/change-requests."""

    reason: Optional[str] = None
    suggestions: Optional[str] = None


class ChangeDecisionIn(BaseModel):
    """Body of PUT /change-requests/<id>/decision."""

    status: Optional[str] = None
    new_slot_id: Optional[int] = None

    @field_validator('new_slot_id', mode='before')
    @classmethod
    def _blank_to_none(cls, value: Any):
        return None if value == '' else value


class MarkStatusIn(BaseModel):
    """Body of POST /<id>/mark-status."""

    status: Optional[str] = Field(None, validate_default=True)
    notes: Optional[str] = None

    @field_validator('status')
    @classmethod
    def _allowed_status(cls, value):
        if value not in ('done', 'no_show'):
            raise ValueError("Estado inválido. Usar 'done' o 'no_show'")
        return value


class CancelIn(BaseModel):
    """Body of POST /<id>/cancel."""

    reason: str = 'Cancelada por coordinador'

    @field_validator('reason', mode='before')
    @classmethod
    def _default_reason(cls, value: Any):
        return 'Cancelada por coordinador' if value in (None, '') else value

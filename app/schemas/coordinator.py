"""Request schemas for /api/v1/coordinator (shape and normalisation only)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ListStudentsQuery(BaseModel):
    """Query string of GET /students. Lenient: a bad `program_id` means "no filter"."""

    model_config = ConfigDict(extra='ignore')

    program_id: Optional[int] = None
    phase: Optional[str] = None
    status: Optional[str] = None
    search: str = ''
    show_other: bool = False

    @field_validator('program_id', mode='before')
    @classmethod
    def _bad_int_is_none(cls, value: Any):
        try:
            return int(value) if value not in (None, '') else None
        except (TypeError, ValueError):
            return None

    @field_validator('phase', 'status', mode='before')
    @classmethod
    def _blank_to_none(cls, value: Any):
        return value or None

    @field_validator('search', mode='before')
    @classmethod
    def _strip_search(cls, value: Any):
        return (value or '').strip()

    @field_validator('show_other', mode='before')
    @classmethod
    def _show_other_flag(cls, value: Any):
        # Only the literal string "true" turned the toggle on.
        return value == 'true' or value is True


class UploadForStudentForm(BaseModel):
    """Multipart fields of POST /upload-for-student (the file is read apart).

    `student_id` / `archive_id` are public UUIDs kept as raw text: resolving
    them (and answering an unknown one exactly like an out-of-scope one) is the
    route's scope guard, not shape validation.
    """

    model_config = ConfigDict(extra='ignore')

    student_id: Optional[str] = None
    archive_id: Optional[str] = None
    notes: str = ''
    decision: str = 'approve'

    @field_validator('notes', mode='before')
    @classmethod
    def _strip_notes(cls, value: Any):
        return (value or '').strip()

    @field_validator('decision', mode='before')
    @classmethod
    def _normalise_decision(cls, value: Any):
        decision = (value or 'approve').strip().lower()
        return decision if decision in ('approve', 'reject') else 'approve'


class StudentHistoryQuery(BaseModel):
    """Query string of GET /students/<uuid>/history."""

    model_config = ConfigDict(extra='ignore')

    format: str = 'formatted'
    limit: int = 50

    @field_validator('limit', mode='after')
    @classmethod
    def _cap_limit(cls, value: int):
        return min(value, 100)

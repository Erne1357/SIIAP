"""Request models for /api/v1/submissions (multipart form fields)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, field_validator


class UploadSubmissionIn(BaseModel):
    """Text fields of POST /api/v1/submissions (the file itself is request.files)."""

    #: Public UUID of the Archive.
    archive_id: Optional[str] = None
    program_id: Optional[int] = None
    program_slug: Optional[str] = None

    @field_validator('program_id', mode='before')
    @classmethod
    def _lenient_int(cls, value: Any):
        # A blank or non-numeric id counts as "not given" (the route then asks
        # for the slug), exactly like `request.form.get(..., type=int)`.
        try:
            return int(value) if value not in (None, '') else None
        except (TypeError, ValueError):
            return None

    @field_validator('archive_id', 'program_slug', mode='before')
    @classmethod
    def _blank_to_none(cls, value: Any):
        return None if value == '' else value

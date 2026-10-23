"""Request schemas for /api/admin/document-templates (shape and normalisation only).

Required-field messages keep their historical text, so the route checks
presence itself; these models only normalise.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class UploadTemplateForm(BaseModel):
    """Multipart text fields of POST / (the file is read apart)."""

    model_config = ConfigDict(extra='ignore')

    name: str = ''
    document_type: str = ''
    program_id: Optional[int] = None
    description: Optional[str] = None

    @field_validator('name', 'document_type', mode='before')
    @classmethod
    def _strip(cls, value: Any):
        return (value or '').strip()

    @field_validator('program_id', mode='before')
    @classmethod
    def _bad_int_is_none(cls, value: Any):
        # Flask's `type=int` yielded None for blank or malformed values.
        try:
            return int(value) if value not in (None, '') else None
        except (TypeError, ValueError):
            return None

    @field_validator('description', mode='before')
    @classmethod
    def _blank_to_none(cls, value: Any):
        return (value or '').strip() or None


class UpdateTemplateIn(BaseModel):
    """Body of PATCH /<uuid>; apply only the keys present (`exclude_unset`)."""

    model_config = ConfigDict(extra='ignore')

    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Any = None


class GenerateDocumentIn(BaseModel):
    """Body of POST /generate. Presence checks stay in the route (legacy message)."""

    model_config = ConfigDict(extra='ignore')

    user_id: Optional[str] = None
    program_id: Optional[int] = None
    document_type: Optional[str] = None
    period_id: Optional[int] = None

    @field_validator('program_id', 'period_id', 'document_type', 'user_id', mode='before')
    @classmethod
    def _blank_to_none(cls, value: Any):
        return None if value == '' else value

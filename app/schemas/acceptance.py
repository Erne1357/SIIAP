"""Request models for /api/v1/acceptance (shape and type checks only).

The "missing field" checks that carry their own error code (MISSING_FIELD,
MISSING_NOTES, ...) stay in the routes; business rules stay in the services.
"""
from __future__ import annotations

from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator


def _text_or_none(value: Any):
    """Stripped text; blank or missing means "not given"."""
    if value is None:
        return None
    return str(value).strip() or None


#: Optional text field, stripped, with blank -> None.
Text = Annotated[Optional[str], BeforeValidator(_text_or_none)]


class DocumentUploadIn(BaseModel):
    """Text fields of POST /user/<uuid>/program/<id>/upload-doc (the file is request.files)."""

    document_type: Text = None


class ReviewReceiptIn(BaseModel):
    """Body of POST /document/<uuid>/review."""

    status: Optional[str] = None
    notes: Optional[str] = None


class ControlNumberIn(BaseModel):
    """Body of POST /user/<uuid>/program/<id>/control-number."""

    control_number: Text = None


class ReasonIn(BaseModel):
    """Body of the defer / request-deferral endpoints."""

    reason: Text = None


class NotesIn(BaseModel):
    """Body of the approve / reject deferral endpoints."""

    notes: Text = None

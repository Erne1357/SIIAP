"""Request models for /api/v1/attendance."""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RegisterToEventIn(BaseModel):
    """Body of POST /api/v1/attendance/event/<id>/register (body optional)."""

    model_config = ConfigDict(extra='ignore')

    notes: Optional[str] = None


class MarkAttendanceIn(BaseModel):
    """Body of POST /api/v1/attendance/event/<id>/mark-attendance."""

    model_config = ConfigDict(extra='ignore')

    user_id: Optional[str] = None  # public UUID
    attended: Optional[bool] = None
    notes: Optional[str] = None
    reset: bool = False

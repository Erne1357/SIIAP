"""Request models for /api/v1/events (shape and type checks only).

Business rules (capacity vs. max_capacity, slot sizes, start < end, ...) stay in
`EventsService`; these models only guarantee that each field has the right type.
"""
import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class CreateEventIn(BaseModel):
    """Body of POST /api/v1/events."""

    model_config = ConfigDict(extra='ignore')

    program_id: Optional[int] = None
    type: Optional[str] = 'interview'
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    visible_to_students: bool = True
    capacity_type: Optional[str] = 'single'
    max_capacity: Optional[int] = None
    requires_registration: bool = True
    allows_attendance_tracking: bool = False
    status: Optional[str] = 'published'
    academic_period_id: Optional[int] = None
    visibility: Optional[str] = 'public'
    reminders_enabled: bool = True

    @field_validator('program_id', 'max_capacity', 'academic_period_id', mode='before')
    @classmethod
    def _blank_to_none(cls, value: Any):
        return None if value == '' else value

    @field_validator(
        'visible_to_students', 'requires_registration',
        'allows_attendance_tracking', 'reminders_enabled',
        mode='before',
    )
    @classmethod
    def _null_bool_is_false(cls, value: Any):
        # The route used to apply bool() to whatever arrived; null meant False.
        return False if value is None else value


class AddWindowIn(BaseModel):
    """Body of POST /api/v1/events/<id>/windows."""

    model_config = ConfigDict(extra='ignore')

    date: dt.date
    start_time: dt.time
    end_time: dt.time
    slot_minutes: int
    timezone: str = 'America/Ciudad_Juarez'

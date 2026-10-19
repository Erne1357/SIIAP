"""Request models for /api/v1/invitations."""
import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class RespondInvitationIn(BaseModel):
    """Body of POST /api/v1/invitations/<id>/respond."""

    model_config = ConfigDict(extra='ignore')

    accept: bool = False


class InviteStudentsIn(BaseModel):
    """Body of POST /api/v1/invitations/event/<id>/invite."""

    model_config = ConfigDict(extra='ignore')

    user_ids: list[Any] = []
    notes: Optional[str] = None
    allow_external: bool = False

    @field_validator('allow_external', mode='before')
    @classmethod
    def _null_bool_is_false(cls, value: Any):
        return False if value is None else value


class UpdateEventDatesIn(BaseModel):
    """Body of PUT /api/v1/invitations/event/<id>/dates (ISO 8601, `Z` allowed)."""

    model_config = ConfigDict(extra='ignore')

    event_date: Optional[dt.datetime] = None
    event_end_date: Optional[dt.datetime] = None

    @field_validator('event_date', 'event_end_date', mode='before')
    @classmethod
    def _blank_to_none(cls, value: Any):
        return None if value == '' else value

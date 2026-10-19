"""Request schemas for /api/v1/retention."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, field_validator, model_validator


class RetentionPolicyIn(BaseModel):
    """Body of POST /policies and PUT /policies/<id>.

    `archive_id` is the public UUID of the Archive; it is only required on
    create (update ignores it), so it is optional here and checked by the route.
    """
    archive_id: Optional[str] = None
    keep_forever: bool = False
    keep_years: Optional[int] = None
    apply_after: str = 'graduated'

    @field_validator('apply_after', mode='before')
    @classmethod
    def _default_apply_after(cls, value: Any) -> Any:
        return value or 'graduated'

    @field_validator('keep_forever', mode='before')
    @classmethod
    def _default_keep_forever(cls, value: Any) -> Any:
        return bool(value) if value is None else value

    @model_validator(mode='after')
    def _years_unless_forever(self):
        if self.keep_forever:
            self.keep_years = None
        elif not self.keep_years or self.keep_years <= 0:
            raise ValueError("Los años de conservación deben ser mayores a 0 si no es «para siempre».")
        return self


class PurgeIn(BaseModel):
    """Body of POST /purge: public UUIDs of the submissions to delete."""
    submission_ids: list[str] = []

    @field_validator('submission_ids', mode='before')
    @classmethod
    def _none_is_empty(cls, value: Any) -> Any:
        return [] if value is None else value

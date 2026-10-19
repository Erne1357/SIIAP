"""Request schemas for /api/v1/archives (shape and normalisation only)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator

_FLAGS = (
    'is_downloadable', 'is_uploadable',
    'allow_coordinator_upload', 'allow_extension_request',
)


class _ArchiveFlags(BaseModel):
    """The four boolean toggles: the API always applied `bool()` to whatever came."""

    model_config = ConfigDict(extra='ignore')

    @field_validator(*_FLAGS, mode='before', check_fields=False)
    @classmethod
    def _truthy(cls, value: Any):
        return bool(value)


class CreateArchiveIn(_ArchiveFlags):
    """Body of POST /api/v1/archives.

    `name` and `step_id` presence/shape are checked by the route so the
    historical messages ("El nombre y la etapa son requeridos.", "step_id
    inválido.") are kept.
    """

    name: str = ''
    step_id: Any = None
    description: Optional[Any] = None
    is_downloadable: bool = False
    is_uploadable: bool = False
    allow_coordinator_upload: bool = False
    allow_extension_request: bool = False

    @field_validator('name', mode='before')
    @classmethod
    def _strip_name(cls, value: Any):
        return (value or '').strip() if isinstance(value, str) or value is None else value


class UpdateArchiveIn(_ArchiveFlags):
    """Body of PUT/PATCH /api/v1/archives/<uuid>.

    Only the keys present in the body are applied: read them with
    `model_dump(exclude_unset=True)`.
    """

    name: Optional[str] = None
    description: Optional[Any] = None
    step_id: Any = None
    is_downloadable: Optional[bool] = None
    is_uploadable: Optional[bool] = None
    allow_coordinator_upload: Optional[bool] = None
    allow_extension_request: Optional[bool] = None

    @field_validator('name', mode='before')
    @classmethod
    def _name_text(cls, value: Any):
        return value if value is None or isinstance(value, str) else str(value)

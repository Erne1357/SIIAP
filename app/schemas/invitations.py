"""Request models for /api/v1/invitations."""
from pydantic import BaseModel, ConfigDict


class RespondInvitationIn(BaseModel):
    """Body of POST /api/v1/invitations/<id>/respond."""

    model_config = ConfigDict(extra='ignore')

    accept: bool = False

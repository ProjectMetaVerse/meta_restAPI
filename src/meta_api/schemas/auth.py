"""Public schemas for Meta authentication and profile flows."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuthorizationResponse(BaseModel):
    """Authorization URL returned to the client."""

    authorization_url: str


class CallbackResponse(BaseModel):
    """Safe callback result; tokens are never returned."""

    user_id: str
    session_established: bool = True


class UserProfile(BaseModel):
    """Normalized public profile contract."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None = None
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    picture_url: str | None = Field(default=None, alias="pictureUrl")
    expires_at: datetime | None = None


class OAuthErrorResponse(BaseModel):
    """Stable error response without upstream details or credentials."""

    detail: str

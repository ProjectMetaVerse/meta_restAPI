"""Version 1 public HTTP payload contracts.

These models are deliberately independent of any web framework so routers can
serialize and validate them without coupling to persistence or upstream clients.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

API_VERSION = "v1"
T = TypeVar("T")


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        ser_json_timedelta="iso8601",
        json_schema_extra={"api_version": API_VERSION},
    )


class OAuthProvider(StrEnum):
    META = "meta"


class AuthInitiationRequest(ContractModel):
    provider: OAuthProvider = OAuthProvider.META
    redirect_uri: str = Field(min_length=1, max_length=2048)
    state: str | None = Field(default=None, min_length=16, max_length=512)


class AuthInitiationResponse(ContractModel):
    provider: OAuthProvider
    authorization_url: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=16, max_length=512)
    expires_at: datetime


class TokenMetadata(ContractModel):
    """Non-secret token metadata; raw access tokens must never cross this boundary."""

    token_type: str = Field(default="bearer", min_length=1, max_length=32)
    expires_at: datetime
    scopes: tuple[str, ...] = ()


class AuthCallbackRequest(ContractModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=16, max_length=512)
    redirect_uri: str = Field(min_length=1, max_length=2048)
    error: str | None = Field(default=None, max_length=128)
    error_description: str | None = Field(default=None, max_length=2048)


class AuthCallbackResponse(ContractModel):
    authenticated: bool = True
    user_id: UUID
    token: TokenMetadata
    request_id: str = Field(min_length=1, max_length=128)


class UserProfileResponse(ContractModel):
    id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=512)
    email: str | None = Field(default=None, max_length=320)
    picture_url: str | None = Field(default=None, max_length=4096)
    provider: OAuthProvider = OAuthProvider.META
    fetched_at: datetime


class EventType(StrEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    PROFILE_VIEW = "profile_view"
    CUSTOM = "custom"


class EventLogRequest(ContractModel):
    event_type: EventType
    occurred_at: datetime
    idempotency_key: str = Field(min_length=8, max_length=256)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def reject_sensitive_metadata_keys(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden = {"access_token", "refresh_token", "client_secret", "authorization", "code"}
        if forbidden.intersection(value):
            raise ValueError("event metadata cannot contain credentials or authorization codes")
        return value


class EventLogResponse(ContractModel):
    id: UUID
    event_type: EventType
    occurred_at: datetime
    idempotency_key: str
    created_at: datetime


class PageInfo(ContractModel):
    next_cursor: str | None = Field(default=None, max_length=512)
    has_more: bool
    limit: int = Field(ge=1, le=100)


class PaginatedResponse(ContractModel, Generic[T]):
    items: list[T]
    page: PageInfo


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"


class HealthResponse(ContractModel):
    status: HealthStatus
    service: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    checked_at: datetime
    dependencies: dict[str, HealthStatus] = Field(default_factory=dict)


class ErrorFieldDetail(ContractModel):
    field: str = Field(min_length=1, max_length=256)
    message: str = Field(min_length=1, max_length=1024)


class ErrorBody(ContractModel):
    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=2048)
    request_id: str = Field(min_length=1, max_length=128)
    fields: list[ErrorFieldDetail] | None = None


class ErrorResponse(ContractModel):
    error: ErrorBody


# Prevent accidental use of SecretStr/raw token types in response contracts.
class InternalToken(ContractModel):
    access_token: SecretStr
    metadata: TokenMetadata

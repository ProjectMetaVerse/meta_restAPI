"""Pydantic schemas for the event-log API."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_EVENT_NAME = 128
MAX_SOURCE = 128
MAX_REFERENCE = 256
MAX_IDEMPOTENCY_KEY = 256
MAX_PAYLOAD_BYTES = 64 * 1024


class EventCreateRequest(BaseModel):
    """Validated event ingestion payload."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=MAX_IDEMPOTENCY_KEY)
    name: str = Field(min_length=1, max_length=MAX_EVENT_NAME)
    source: str = Field(min_length=1, max_length=MAX_SOURCE)
    actor_ref: str | None = Field(default=None, max_length=MAX_REFERENCE)
    session_ref: str | None = Field(default=None, max_length=MAX_REFERENCE)
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    @field_validator("idempotency_key", "name", "source", "actor_ref", "session_ref")
    @classmethod
    def reject_control_or_blank_values(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or any(ord(char) < 32 for char in value)):
            raise ValueError("string fields must not be blank or contain control characters")
        return value

    @field_validator("payload")
    @classmethod
    def validate_payload_size_and_values(cls, value: dict[str, Any]) -> dict[str, Any]:
        import json

        try:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("payload must contain JSON-compatible values") from exc
        if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"payload must be at most {MAX_PAYLOAD_BYTES} bytes")
        return value

    @field_validator("occurred_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(UTC)


class EventResponse(BaseModel):
    """Stable public event response."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str
    idempotency_key: str
    name: str
    source: str
    actor_ref: str | None
    session_ref: str | None
    payload: dict[str, Any]
    occurred_at: datetime
    received_at: datetime
    status: str


class EventCreateResponse(BaseModel):
    """Stable ingestion response with replay indication."""

    event: EventResponse
    replayed: bool


class EventPageResponse(BaseModel):
    """Bounded event listing response."""

    items: list[EventResponse]
    next_cursor: str | None

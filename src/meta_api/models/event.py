"""Event domain model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Event:
    """A durable, append-oriented application event."""

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


@dataclass(frozen=True, slots=True)
class EventPage:
    """A bounded page of events ordered newest first."""

    items: list[Event]
    next_cursor: str | None


class EventRepositoryError(RuntimeError):
    """Raised when event persistence cannot complete."""


class EventConflictError(RuntimeError):
    """Raised when an idempotency key is reused with different content."""


class EventNotFoundError(LookupError):
    """Raised when an event does not exist."""


class EventRepository:
    """Persistence boundary for event storage."""

    async def initialize(self) -> None:
        raise NotImplementedError

    async def save(self, event: Event) -> Event:
        raise NotImplementedError

    async def get(self, event_id: str) -> Event | None:
        raise NotImplementedError

    async def get_by_idempotency_key(self, key: str) -> Event | None:
        raise NotImplementedError

    async def list(self, *, limit: int, before: tuple[datetime, str] | None = None) -> EventPage:
        raise NotImplementedError

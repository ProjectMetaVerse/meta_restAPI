"""Dependency inversion boundaries for endpoint implementations."""

from datetime import datetime
from pathlib import Path
from typing import Protocol, Sequence
from uuid import UUID

from ..contracts.v1 import EventLogRequest, EventLogResponse, UserProfileResponse


class MetaGraphClient(Protocol):
    """Only adapter allowed to know Graph URLs, API versions, and Meta payloads."""

    async def exchange_code(self, code: str, redirect_uri: str) -> "GraphToken": ...

    async def fetch_user_profile(self, access_token: str) -> "GraphProfile": ...


class TokenSessionStore(Protocol):
    async def put(self, user_id: UUID, token: "StoredToken") -> None: ...
    async def get(self, user_id: UUID) -> "StoredToken | None": ...
    async def revoke(self, user_id: UUID) -> None: ...


class UserProfileService(Protocol):
    async def get_profile(self, user_id: UUID) -> UserProfileResponse: ...


class EventRepository(Protocol):
    async def append(self, user_id: UUID, event: EventLogRequest) -> EventLogResponse: ...
    async def find_by_idempotency_key(self, user_id: UUID, key: str) -> EventLogResponse | None: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class RequestIDProvider(Protocol):
    def request_id(self) -> str: ...


class GraphToken(Protocol):
    access_token: str
    expires_at: datetime
    scopes: Sequence[str]


class GraphProfile(Protocol):
    id: str
    name: str
    email: str | None
    picture_url: str | None


class StoredToken(Protocol):
    """Storage-only token shape; never serialize or log this object."""

    access_token: str
    expires_at: datetime
    scopes: Sequence[str]

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from meta_api.core.config import Settings
from meta_api.main import create_app
from meta_api.models.event import Event, EventPage


class FakeEventRepository:
    def __init__(self) -> None:
        self.events: dict[str, Event] = {}
        self.keys: dict[str, Event] = {}
        self.initialized = False
        self.fail_save = False
        self.fail_get = False
        self.fail_list = False

    async def initialize(self) -> None:
        self.initialized = True

    async def get_by_idempotency_key(self, key: str) -> Event | None:
        return self.keys.get(key)

    async def save(self, event: Event) -> Event:
        if self.fail_save:
            from meta_api.models.event import EventRepositoryError

            raise EventRepositoryError("fake persistence failure")
        self.events[event.event_id] = event
        self.keys[event.idempotency_key] = event
        return event

    async def get(self, event_id: str) -> Event | None:
        if self.fail_get:
            from meta_api.models.event import EventRepositoryError

            raise EventRepositoryError("fake persistence failure")
        return self.events.get(event_id)

    async def list(self, limit: int, before: tuple[datetime, str] | None = None) -> EventPage:
        if self.fail_list:
            from meta_api.models.event import EventRepositoryError

            raise EventRepositoryError("fake persistence failure")
        events = sorted(
            self.events.values(), key=lambda item: (item.occurred_at, item.event_id), reverse=True
        )
        if before:
            events = [event for event in events if (event.occurred_at, event.event_id) < before]
        page = events[:limit]
        next_cursor = None
        if len(events) > limit:
            last = page[-1]
            next_cursor = last.occurred_at.isoformat() + "|" + last.event_id
        return EventPage(items=page, next_cursor=next_cursor)


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, 678901, tzinfo=UTC)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test", database_url=f"sqlite+aiosqlite:///{tmp_path / 'events.db'}"
    )


@pytest.fixture
def authenticated_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'events.db'}",
        event_read_token="read-secret",
    )


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_headers() -> dict[str, str]:
    return {"Authorization": "Bearer read-secret"}


@pytest.fixture
def fake_repository() -> FakeEventRepository:
    return FakeEventRepository()


@pytest.fixture
def async_transport() -> httpx.MockTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "profile-1", "name": "Test User"}, request=request)

    return httpx.MockTransport(handler)


@pytest.fixture
async def async_client(async_transport: httpx.MockTransport) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=async_transport) as client:
        yield client

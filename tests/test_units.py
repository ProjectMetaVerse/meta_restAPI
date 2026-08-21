from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from meta_api.clients.graph_api import GraphAPIClient
from meta_api.core.config import Settings
from meta_api.core.logging import StructuredFormatter
from meta_api.models.event import EventConflictError
from meta_api.schemas.events import EventCreateRequest
from meta_api.services.events import EventService


def test_settings_normalize_level_and_require_production_values() -> None:
    assert Settings(log_level="warning").log_level == "WARNING"
    with pytest.raises(ValidationError, match="meta_app_id"):
        Settings(environment="production")
    with pytest.raises(ValidationError, match="log_level"):
        Settings(log_level="verbose")


def test_settings_accepts_complete_production_configuration() -> None:
    configured = Settings(
        environment="production",
        meta_app_id="app-id",
        meta_app_secret="app-secret",
        redirect_uri="https://example.test/callback",
        encryption_key="encryption",
        signing_key="signing",
    )
    assert configured.meta_app_secret is not None
    assert configured.meta_app_secret.get_secret_value() == "app-secret"


@pytest.mark.parametrize(
    "payload",
    [
        {"idempotency_key": "", "name": "n", "source": "s"},
        {"idempotency_key": "x", "name": "n\n", "source": "s"},
        {"idempotency_key": "x", "name": "n", "source": "s", "payload": {"x": {1, 2}}},
        {"idempotency_key": "x", "name": "n", "source": "s", "occurred_at": "2026-01-01T00:00:00"},
    ],
)
def test_event_schema_rejects_unsafe_or_invalid_input(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EventCreateRequest.model_validate(payload)


def test_event_schema_normalizes_aware_timestamp_and_forbids_extra_fields() -> None:
    event = EventCreateRequest.model_validate(
        {
            "idempotency_key": "key",
            "name": "purchase",
            "source": "checkout",
            "occurred_at": "2026-01-01T01:00:00+01:00",
            "payload": {"amount": 10},
        }
    )
    assert event.occurred_at == datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        EventCreateRequest.model_validate(
            {"idempotency_key": "key", "name": "n", "source": "s", "extra": True}
        )


@pytest.mark.asyncio
async def test_graph_client_constructs_versioned_request(
    async_client: httpx.AsyncClient, settings: Settings
) -> None:
    client = GraphAPIClient(
        settings.model_copy(update={"graph_api_base_url": "https://graph.test/"}), async_client
    )
    result = await client.get("/me", fields="id,name")
    assert result["id"] == "profile-1"
    request = await async_client.get("https://graph.test/v21.0/me", params={"fields": "id,name"})
    assert request.url.path == "/v21.0/me"


@pytest.mark.asyncio
async def test_graph_client_maps_http_errors_without_live_network(settings: Settings) -> None:
    request_seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_seen.append(request)
        return httpx.Response(401, json={"error": {"message": "invalid token"}}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mocked:
        client = GraphAPIClient(settings, mocked)
        with pytest.raises(httpx.HTTPStatusError) as error:
            await client.get("me", access_token="redacted")
    assert error.value.response.status_code == 401
    assert request_seen[0].url.params["access_token"] == "redacted"


@pytest.mark.asyncio
async def test_event_service_replays_and_rejects_conflicting_idempotency(fake_repository) -> None:
    service = EventService(fake_repository)
    request = EventCreateRequest.model_validate(
        {"idempotency_key": "same", "name": "created", "source": "test", "payload": {"x": 1}}
    )
    first, replayed = await service.ingest(request)
    assert replayed is False
    second, replayed = await service.ingest(request)
    assert second == first
    assert replayed is True
    with pytest.raises(EventConflictError):
        await service.ingest(request.model_copy(update={"name": "different"}))


def test_structured_formatter_omits_sensitive_log_extras() -> None:
    import logging

    record = logging.LogRecord("meta", logging.INFO, __file__, 1, "event accepted", (), None)
    record.payload = {"token": "never-log"}
    record.request_id = "req-1"
    formatted = StructuredFormatter().format(record)
    assert "event accepted" in formatted
    assert "never-log" not in formatted
    assert "req-1" not in formatted

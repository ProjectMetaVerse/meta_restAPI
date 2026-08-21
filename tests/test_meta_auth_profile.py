"""Unit and endpoint coverage for Meta OAuth and profile flows."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from meta_api.clients.meta_graph import MetaGraphClient
from meta_api.core.config import Settings
from meta_api.exceptions.base import InvalidUpstreamPayloadError, MetaUpstreamError
from meta_api.main import create_app
from meta_api.repositories.auth import AuthSession


def settings() -> Settings:
    return Settings(
        environment="test",
        meta_app_id="app-id",
        meta_app_secret="app-secret",
        redirect_uri="https://example.com/meta/callback",
        secure_cookies=False,
    )


@pytest.mark.asyncio
async def test_graph_client_success_and_request_id() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["request_id"] = request.headers["X-Request-ID"]
        return httpx.Response(200, json={"id": "u1"})

    result = await MetaGraphClient(
        "https://graph.example", "v21.0", transport=httpx.MockTransport(handler)
    ).request("GET", "me", request_id="req-1")
    assert result == {"id": "u1"}
    assert seen == {"url": "https://graph.example/v21.0/me", "request_id": "req-1"}


@pytest.mark.asyncio
async def test_graph_client_malformed_payload() -> None:
    client = MetaGraphClient(
        "https://graph.example",
        "v21.0",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="nope")),
    )
    with pytest.raises(InvalidUpstreamPayloadError):
        await client.request("GET", "me")


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [httpx.Response(429), httpx.Response(503)])
async def test_graph_client_rate_limit_and_server_failure_are_bounded(
    response: httpx.Response,
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response

    client = MetaGraphClient(
        "https://graph.example", "v21.0", max_retries=1, transport=httpx.MockTransport(handler)
    )
    with pytest.raises(MetaUpstreamError, match="temporarily unavailable"):
        await client.request("GET", "me")
    assert calls == 2


@pytest.mark.asyncio
async def test_graph_client_timeout_is_stable() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    client = MetaGraphClient(
        "https://graph.example", "v21.0", max_retries=0, transport=httpx.MockTransport(handler)
    )
    with pytest.raises(MetaUpstreamError, match="temporarily unavailable"):
        await client.request("GET", "me")


@pytest.mark.asyncio
async def test_graph_client_meta_error_is_redacted() -> None:
    client = MetaGraphClient(
        "https://graph.example",
        "v21.0",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(400, json={"error": {"message": "secret-token"}})
        ),
    )
    with pytest.raises(MetaUpstreamError) as error:
        await client.request("GET", "me")
    assert "secret-token" not in str(error.value)


def test_authorization_endpoint_validates_configuration_and_returns_state() -> None:
    app = create_app(settings())
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/meta/authorize")
    assert response.status_code == 200
    assert "state=" in response.json()["authorization_url"]
    assert "scope=public_profile%2Cemail" in response.json()["authorization_url"]


def test_callback_rejects_invalid_state() -> None:
    app = create_app(settings())
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/meta/callback?code=abc&state=wrong")
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid OAuth callback"}


def test_callback_and_profile_endpoint() -> None:
    app = create_app(settings())
    app.state.auth_service.client = MetaGraphClient(
        "https://graph.example",
        "v21.0",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"access_token": "token", "user_id": "u1", "expires_in": 3600}
            )
        ),
    )
    with TestClient(app) as client:
        authorization = client.get("/api/v1/auth/meta/authorize").json()["authorization_url"]
        state = authorization.split("state=", 1)[1].split("&", 1)[0]
        callback = client.get(f"/api/v1/auth/meta/callback?code=abc&state={state}")
    assert callback.status_code == 200
    assert callback.json() == {"user_id": "u1", "session_established": True}
    assert "token" not in callback.text


def test_profile_requires_authentication_and_exposes_only_normalized_fields() -> None:
    app = create_app(settings())
    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/users/me")
    assert unauthorized.status_code == 401
    session_id = "session-1"
    app.state.auth_repository._sessions[session_id] = AuthSession(
        session_id, "u1", "token", datetime.now(UTC) + timedelta(hours=1)
    )
    app.state.profile_service.client = MetaGraphClient(
        "https://graph.example",
        "v21.0",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "id": "u1",
                    "name": "Ada",
                    "secret": "drop",
                    "picture": {"data": {"url": "https://img.example/a"}},
                },
            )
        ),
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {session_id}"})
    assert response.status_code == 200
    assert response.json()["id"] == "u1"
    assert response.json()["picture_url"] == "https://img.example/a"
    assert "secret" not in response.json()

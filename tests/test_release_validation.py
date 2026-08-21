from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from meta_api.clients.graph_api import GraphAPIClient
from meta_api.core.config import Settings
from meta_api.main import create_app


def test_production_settings_fail_closed_when_required_values_are_missing() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, environment="production")

    message = str(error.value)
    assert "meta_app_id" in message
    assert "meta_app_secret" in message
    assert "redirect_uri" in message
    assert "encryption_key" in message
    assert "signing_key" in message


def test_production_settings_accept_explicit_non_secret_test_values() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        meta_app_id="test-app-id",
        meta_app_secret="test-app-secret",
        redirect_uri="https://example.test/callback",
        encryption_key="test-encryption-key",
        signing_key="test-signing-key",
    )

    assert settings.environment == "production"
    assert settings.meta_app_secret is not None
    assert settings.meta_app_secret.get_secret_value() == "test-app-secret"


def test_non_production_docs_and_openapi_are_available(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health").json()["status"] == "ok"
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        openapi = client.get("/openapi.json")

    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == settings.app_name


def test_production_docs_are_disabled(settings: Settings) -> None:
    production = Settings(
        _env_file=None,
        environment="production",
        meta_app_id="test-app-id",
        meta_app_secret="test-app-secret",
        redirect_uri="https://example.test/callback",
        encryption_key="test-encryption-key",
        signing_key="test-signing-key",
        database_url=settings.database_url,
    )

    with TestClient(create_app(production)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/api/v1/health").status_code == 200


def test_graph_client_boundary_is_mockable_without_network(settings: Settings) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "profile-1"}, request=request)

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
            client = GraphAPIClient(settings, transport)
            return await client.get("me", fields="id")

    response = asyncio.run(run())

    assert response == {"id": "profile-1"}
    assert str(requests[0].url) == (
        f"{settings.graph_api_base_url}/{settings.graph_api_version}/me?fields=id"
    )


def test_env_example_contains_placeholders_only() -> None:
    env_example = Path(__file__).parents[1] / ".env.example"
    content = env_example.read_text(encoding="utf-8")

    assert "ghp_" not in content
    assert "sk-" not in content
    assert "BEGIN PRIVATE KEY" not in content
    assert "your-meta-app-secret" in content
    assert "replace-with-a-secret" in content
    assert "META_EVENT_READ_TOKEN=" in content

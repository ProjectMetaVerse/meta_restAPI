from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from meta_api.clients.graph_api import GraphAPIClient
from meta_api.main import create_app


def test_health_and_openapi_expose_representative_contracts(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["service"] == "meta-restapi"

    document = client.get("/openapi.json")
    assert document.status_code == 200
    paths = document.json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/events" in paths
    assert paths["/api/v1/events"]["post"]["responses"]["202"]["content"]["application/json"][
        "schema"
    ]


def test_event_create_replay_and_request_id_are_deterministic(client: TestClient) -> None:
    body = {
        "idempotency_key": "integration-1",
        "name": "checkout.completed",
        "source": "test",
        "payload": {"ok": True},
    }
    first = client.post("/api/v1/events", json=body, headers={"X-Request-ID": "req-integration"})
    replay = client.post("/api/v1/events", json=body)
    assert first.status_code == 202
    assert first.headers["X-Request-ID"] == "req-integration"
    assert first.json()["replayed"] is False
    assert replay.status_code == 202
    assert replay.json()["replayed"] is True
    assert replay.json()["event"]["event_id"] == first.json()["event"]["event_id"]


def test_event_get_not_found_and_read_authorization(authenticated_settings) -> None:
    app = create_app(authenticated_settings)
    with TestClient(app) as client:
        denied = client.get("/api/v1/events/missing")
        allowed_missing = client.get(
            "/api/v1/events/missing", headers={"Authorization": "Bearer read-secret"}
        )
    assert denied.status_code == 403
    assert allowed_missing.status_code == 404
    assert allowed_missing.json()["detail"] == "event not found"


def test_validation_conflict_and_bad_cursor_errors(client: TestClient) -> None:
    unknown = client.post(
        "/api/v1/events", json={"idempotency_key": "x", "name": "n", "source": "s", "extra": 1}
    )
    assert unknown.status_code == 422
    body = {"idempotency_key": "conflict", "name": "first", "source": "test"}
    assert client.post("/api/v1/events", json=body).status_code == 202
    conflict = client.post("/api/v1/events", json={**body, "name": "second"})
    assert conflict.status_code == 409
    bad_cursor = client.get("/api/v1/events?before=not-a-cursor")
    assert bad_cursor.status_code == 422
    assert client.get("/api/v1/events?limit=101").status_code == 422


def test_event_persistence_failure_maps_to_503(client: TestClient) -> None:
    from meta_api.models.event import EventRepositoryError

    class FailingRepository:
        async def get_by_idempotency_key(self, key: str):
            return None

        async def save(self, event):
            raise EventRepositoryError("fake persistence failure")

    client.app.state.event_repository = FailingRepository()
    response = client.post(
        "/api/v1/events", json={"idempotency_key": "failure", "name": "n", "source": "s"}
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "event persistence unavailable"


def test_paginated_event_listing_requires_token_and_returns_cursor(authenticated_settings) -> None:
    app = create_app(authenticated_settings)
    headers = {"Authorization": "Bearer read-secret"}
    with TestClient(app) as client:
        for key in ("one", "two", "three"):
            assert (
                client.post(
                    "/api/v1/events", json={"idempotency_key": key, "name": "n", "source": "s"}
                ).status_code
                == 202
            )
        assert client.get("/api/v1/events").status_code == 403
        page = client.get("/api/v1/events?limit=2", headers=headers)
        assert page.status_code == 200
        assert len(page.json()["items"]) == 2
        assert page.json()["next_cursor"]
        next_page = client.get(
            "/api/v1/events?limit=2&before=" + page.json()["next_cursor"], headers=headers
        )
        assert next_page.status_code == 200
        assert len(next_page.json()["items"]) == 1


def test_graph_timeout_is_isolated_and_deterministic(settings) -> None:
    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timed out", request=request)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as mocked:
            client = GraphAPIClient(settings, mocked)
            try:
                await client.get("me")
            except httpx.ReadTimeout as exc:
                assert "timed out" in str(exc)
            else:
                raise AssertionError("timeout should propagate from the client boundary")

    import asyncio

    asyncio.run(run())

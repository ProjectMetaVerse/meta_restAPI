"""Event repository and API tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meta_api.core.config import Settings
from meta_api.main import create_app
from meta_api.models.event import Event, EventConflictError
from meta_api.repositories.events import SQLiteEventRepository


def make_settings(tmp_path: Path, **kwargs: object) -> Settings:
    return Settings(
        environment="test", database_url=f"sqlite+aiosqlite:///{tmp_path / 'events.db'}", **kwargs
    )


def test_event_ingestion_is_idempotent_and_serializes_metadata(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    payload = {
        "idempotency_key": "checkout-1",
        "name": "checkout.completed",
        "source": "web",
        "payload": {"order_id": "o-1", "nested": {"ok": True}},
    }
    with TestClient(app) as client:
        first = client.post("/api/v1/events", json=payload, headers={"X-Request-ID": "req-1"})
        second = client.post("/api/v1/events", json=payload)
    assert first.status_code == 202
    assert first.headers["X-Request-ID"] == "req-1"
    assert second.status_code == 202
    assert first.json()["replayed"] is False
    assert second.json()["replayed"] is True
    assert first.json()["event"]["event_id"] == second.json()["event"]["event_id"]
    assert second.json()["event"]["payload"]["nested"]["ok"] is True


def test_conflicting_replay_is_rejected(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        body = {"idempotency_key": "same", "name": "a", "source": "test", "payload": {}}
        assert client.post("/api/v1/events", json=body).status_code == 202
        body["name"] = "b"
        response = client.post("/api/v1/events", json=body)
    assert response.status_code == 409


def test_validation_enforces_extra_fields_payload_size_and_timezone(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        extra = client.post(
            "/api/v1/events",
            json={"idempotency_key": "x", "name": "n", "source": "s", "unknown": 1},
        )
        oversized = client.post(
            "/api/v1/events",
            json={
                "idempotency_key": "y",
                "name": "n",
                "source": "s",
                "payload": {"x": "a" * 70000},
            },
        )
        naive = client.post(
            "/api/v1/events",
            json={
                "idempotency_key": "z",
                "name": "n",
                "source": "s",
                "occurred_at": "2026-01-01T00:00:00",
            },
        )
    assert extra.status_code == 422
    assert oversized.status_code == 422
    assert naive.status_code == 422


def test_retrieval_paginates_and_enforces_read_token(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path, event_read_token="read-secret"))
    with TestClient(app) as client:
        for number in range(3):
            assert (
                client.post(
                    "/api/v1/events",
                    json={"idempotency_key": str(number), "name": "test", "source": "suite"},
                ).status_code
                == 202
            )
        denied = client.get("/api/v1/events")
        page = client.get("/api/v1/events?limit=2", headers={"Authorization": "Bearer read-secret"})
        next_page = client.get(
            f"/api/v1/events?limit=2&before={page.json()['next_cursor']}",
            headers={"Authorization": "Bearer read-secret"},
        )
    assert denied.status_code == 403
    assert page.status_code == 200
    assert len(page.json()["items"]) == 2
    assert next_page.status_code == 200
    assert len(next_page.json()["items"]) == 1


@pytest.mark.asyncio
async def test_repository_rollback_and_duplicate_conflict(tmp_path: Path) -> None:
    repository = SQLiteEventRepository(f"sqlite+aiosqlite:///{tmp_path / 'repo.db'}")
    await repository.initialize()
    event = Event(
        "id-1",
        "key-1",
        "name",
        "source",
        None,
        None,
        {"a": 1},
        __import__("datetime").datetime.now(__import__("datetime").UTC),
        __import__("datetime").datetime.now(__import__("datetime").UTC),
        "accepted",
    )
    assert await repository.save(event) == event
    assert await repository.save(event) == event
    conflicting = Event(
        "id-2",
        "key-1",
        "other",
        "source",
        None,
        None,
        {"a": 2},
        event.occurred_at,
        event.received_at,
        "accepted",
    )
    with pytest.raises(EventConflictError):
        await repository.save(conflicting)
    assert await repository.get("id-2") is None


def test_event_payload_is_not_written_to_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    app = create_app(make_settings(tmp_path))
    secret = "do-not-log-this"
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/events",
            json={
                "idempotency_key": "log",
                "name": "safe",
                "source": "test",
                "payload": {"secret": secret},
            },
        )
    assert response.status_code == 202
    assert secret not in caplog.text

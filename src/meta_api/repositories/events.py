"""SQLite event repository; SQL remains behind the repository boundary."""

import asyncio
import base64
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from meta_api.models.event import (
    Event,
    EventConflictError,
    EventPage,
    EventRepository,
    EventRepositoryError,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    actor_ref TEXT,
    session_ref TEXT,
    payload_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events (occurred_at DESC, event_id DESC);
CREATE INDEX IF NOT EXISTS idx_events_received_at ON events (received_at DESC, event_id DESC);
"""


def _parse_sqlite_path(database_url: str) -> str:
    if database_url == ":memory:" or database_url == "sqlite:///:memory:":
        return ":memory:"
    if database_url.startswith("sqlite+aiosqlite:///"):
        return database_url.removeprefix("sqlite+aiosqlite:///")
    if database_url.startswith("sqlite:///"):
        return database_url.removeprefix("sqlite:///")
    raise ValueError("Only SQLite database URLs are supported by the default event repository")


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _event_from_row(row: sqlite3.Row) -> Event:
    return Event(
        event_id=row["event_id"],
        idempotency_key=row["idempotency_key"],
        name=row["name"],
        source=row["source"],
        actor_ref=row["actor_ref"],
        session_ref=row["session_ref"],
        payload=json.loads(row["payload_json"]),
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
        received_at=datetime.fromisoformat(row["received_at"]),
        status=row["status"],
    )


class SQLiteEventRepository(EventRepository):
    """Durable repository using one short-lived SQLite connection per operation."""

    def __init__(self, database_url: str) -> None:
        self.database_path = _parse_sqlite_path(database_url)
        if self.database_path != ":memory:":
            Path(self.database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    async def save(self, event: Event) -> Event:
        return await asyncio.to_thread(self._save, event)

    def _save(self, event: Event) -> Event:
        payload = json.dumps(event.payload, ensure_ascii=False, separators=(",", ":"))
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM events WHERE idempotency_key = ?", (event.idempotency_key,)
            ).fetchone()
            if existing is not None:
                stored = _event_from_row(existing)
                if (stored.name, stored.source, stored.payload) != (
                    event.name,
                    event.source,
                    event.payload,
                ):
                    raise EventConflictError(
                        "idempotency key was already used for a different event"
                    )
                connection.rollback()
                return stored
            connection.execute(
                """INSERT INTO events
                (event_id, idempotency_key, name, source, actor_ref, session_ref, payload_json,
                 occurred_at, received_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id,
                    event.idempotency_key,
                    event.name,
                    event.source,
                    event.actor_ref,
                    event.session_ref,
                    payload,
                    _iso(event.occurred_at),
                    _iso(event.received_at),
                    event.status,
                ),
            )
            connection.commit()
            return event
        except EventConflictError:
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise EventRepositoryError("event persistence failed") from exc
        finally:
            connection.close()

    async def get(self, event_id: str) -> Event | None:
        return await asyncio.to_thread(self._get, event_id)

    def _get(self, event_id: str) -> Event | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM events WHERE event_id = ?", (event_id,)
                ).fetchone()
                return _event_from_row(row) if row else None
        except sqlite3.Error as exc:
            raise EventRepositoryError("event lookup failed") from exc

    async def get_by_idempotency_key(self, key: str) -> Event | None:
        return await asyncio.to_thread(self._get_by_key, key)

    def _get_by_key(self, key: str) -> Event | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM events WHERE idempotency_key = ?", (key,)
                ).fetchone()
                return _event_from_row(row) if row else None
        except sqlite3.Error as exc:
            raise EventRepositoryError("event lookup failed") from exc

    async def list(self, *, limit: int, before: tuple[datetime, str] | None = None) -> EventPage:
        return await asyncio.to_thread(self._list, limit, before)

    def _list(self, limit: int, before: tuple[datetime, str] | None) -> EventPage:
        try:
            with self._connect() as connection:
                params: list[Any] = []
                where = ""
                if before is not None:
                    timestamp, event_id = before
                    where = "WHERE occurred_at < ? OR (occurred_at = ? AND event_id < ?)"
                    params.extend((_iso(timestamp), _iso(timestamp), event_id))
                rows = connection.execute(
                    f"SELECT * FROM events {where} ORDER BY occurred_at DESC, "
                    "event_id DESC LIMIT ?",
                    (*params, limit + 1),
                ).fetchall()
                has_more = len(rows) > limit
                items = [_event_from_row(row) for row in rows[:limit]]
                next_cursor = (
                    base64.urlsafe_b64encode(
                        f"{_iso(items[-1].occurred_at)}|{items[-1].event_id}".encode()
                    ).decode()
                    if has_more and items
                    else None
                )
                return EventPage(items=items, next_cursor=next_cursor)
        except sqlite3.Error as exc:
            raise EventRepositoryError("event listing failed") from exc

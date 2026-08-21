"""Event ingestion use case."""

from datetime import UTC, datetime
from uuid import uuid4

from meta_api.models.event import Event, EventConflictError, EventRepository
from meta_api.schemas.events import EventCreateRequest


class EventService:
    """Coordinates validation-ready event requests and repository persistence."""

    def __init__(self, repository: EventRepository) -> None:
        self.repository = repository

    async def ingest(self, request: EventCreateRequest) -> tuple[Event, bool]:
        existing = await self.repository.get_by_idempotency_key(request.idempotency_key)
        if existing is not None:
            if (existing.name, existing.source, existing.payload) != (
                request.name,
                request.source,
                request.payload,
            ):
                raise EventConflictError("idempotency key was already used for a different event")
            return existing, True
        now = datetime.now(UTC)
        event = Event(
            event_id=str(uuid4()),
            idempotency_key=request.idempotency_key,
            name=request.name,
            source=request.source,
            actor_ref=request.actor_ref,
            session_ref=request.session_ref,
            payload=request.payload,
            occurred_at=request.occurred_at or now,
            received_at=now,
            status="accepted",
        )
        stored = await self.repository.save(event)
        return stored, stored.event_id != event.event_id

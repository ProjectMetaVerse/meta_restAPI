from __future__ import annotations

import base64
import binascii
import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status

from meta_api.core.config import Settings
from meta_api.models.event import EventConflictError, EventRepositoryError
from meta_api.schemas.events import (
    EventCreateRequest,
    EventCreateResponse,
    EventPageResponse,
    EventResponse,
)
from meta_api.services.events import EventService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])
MAX_PAGE_SIZE = 100


def event_service(request: Request) -> EventService:
    return EventService(request.app.state.event_repository)


event_service_dependency = Depends(event_service)


def _correlation_id(request: Request) -> str:
    value = request.headers.get("X-Request-ID", "").strip()
    return value[:128] if value else str(uuid4())


def _authorize_read(request: Request, authorization: str | None) -> None:
    settings: Settings = request.app.state.settings
    configured = settings.event_read_token.get_secret_value() if settings.event_read_token else None
    if configured and authorization != f"Bearer {configured}":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="event read access denied"
        )


def _persistence_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="event persistence unavailable",
    )


@router.post("/events", response_model=EventCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_event(
    request: Request,
    response: Response,
    body: EventCreateRequest,
    service: EventService = event_service_dependency,
) -> EventCreateResponse:
    correlation_id = _correlation_id(request)
    response.headers["X-Request-ID"] = correlation_id
    try:
        event, replayed = await service.ingest(body)
    except EventConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except EventRepositoryError as exc:
        logger.exception("event_persistence_error", extra={"request_id": correlation_id})
        raise _persistence_unavailable() from exc
    logger.info(
        "event_accepted",
        extra={"request_id": correlation_id, "event_id": event.event_id, "event_name": event.name},
    )
    return EventCreateResponse(event=EventResponse.model_validate(event), replayed=replayed)


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> EventResponse:
    response.headers["X-Request-ID"] = _correlation_id(request)
    _authorize_read(request, authorization)
    try:
        event = await request.app.state.event_repository.get(event_id)
    except EventRepositoryError as exc:
        logger.exception("event_lookup_error")
        raise _persistence_unavailable() from exc
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="event not found")
    return EventResponse.model_validate(event)


@router.get("/events", response_model=EventPageResponse)
async def list_events(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    before: str | None = Query(default=None, max_length=128),
    authorization: str | None = Header(default=None),
) -> EventPageResponse:
    response.headers["X-Request-ID"] = _correlation_id(request)
    _authorize_read(request, authorization)
    cursor = None
    if before:
        try:
            decoded = base64.urlsafe_b64decode(before.encode()).decode()
            timestamp, event_id = decoded.rsplit("|", 1)
            if not event_id:
                raise ValueError("missing event id")
            cursor = (datetime.fromisoformat(timestamp), event_id)
        except (ValueError, UnicodeError, binascii.Error) as exc:
            raise HTTPException(
                status_code=422, detail="before must be a valid event cursor"
            ) from exc
    try:
        page = await request.app.state.event_repository.list(limit=limit, before=cursor)
    except EventRepositoryError as exc:
        logger.exception("event_listing_error")
        raise _persistence_unavailable() from exc
    return EventPageResponse(
        items=[EventResponse.model_validate(event) for event in page.items],
        next_cursor=page.next_cursor,
    )

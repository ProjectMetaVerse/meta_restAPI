"""Service health endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Minimal liveness response."""

    status: str
    service: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse, summary="Service health")
async def health_check() -> HealthResponse:
    """Report whether the HTTP process is accepting requests."""
    return HealthResponse(
        status="ok",
        service="meta-restapi",
        timestamp=datetime.now(UTC),
    )


@router.get("/ready", response_model=HealthResponse, summary="Service readiness")
async def readiness(request: Request, response: Response) -> HealthResponse:
    ready = bool(getattr(request.app.state, "ready", False))
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ready" if ready else "not_ready",
        service="meta-restapi",
        timestamp=datetime.now(UTC),
    )

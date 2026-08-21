"""Service health endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter
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

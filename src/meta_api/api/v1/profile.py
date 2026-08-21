"""Authenticated Meta profile endpoint."""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from meta_api.dependencies.auth import authenticated_session
from meta_api.exceptions.base import (
    AuthenticationError,
    InvalidUpstreamPayloadError,
    MetaUpstreamError,
)
from meta_api.schemas.auth import UserProfile
from meta_api.services.profile import ProfileService

router = APIRouter(prefix="/users", tags=["profile"])


def service(request: Request) -> ProfileService:
    return cast(ProfileService, request.app.state.profile_service)


@router.get("/me", response_model=UserProfile, response_model_by_alias=False)
async def profile(
    request: Request, session_id: str = Depends(authenticated_session)
) -> UserProfile:
    try:
        return await service(request).get_profile(session_id)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        ) from exc
    except InvalidUpstreamPayloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Profile service returned an invalid response",
        ) from exc
    except MetaUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Profile service unavailable"
        ) from exc

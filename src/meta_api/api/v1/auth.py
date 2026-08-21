"""Meta OAuth endpoints."""

from typing import cast

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from meta_api.schemas.auth import AuthorizationResponse, CallbackResponse
from meta_api.services.auth import AuthService

router = APIRouter(prefix="/auth/meta", tags=["authentication"])


def service(request: Request) -> AuthService:
    return cast(AuthService, request.app.state.auth_service)


@router.get("/authorize", response_model=AuthorizationResponse)
async def authorize(request: Request) -> AuthorizationResponse:
    try:
        return AuthorizationResponse(authorization_url=await service(request).authorization_url())
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="OAuth is not configured") from exc


@router.get("/callback", response_model=CallbackResponse)
async def callback(
    request: Request,
    response: Response,
    code: str = Query(min_length=1),
    state: str = Query(min_length=1),
) -> CallbackResponse:
    try:
        session_id, user_id = await service(request).callback(code, state)
    except Exception as exc:
        from meta_api.exceptions.base import OAuthCodeError, OAuthStateError

        if isinstance(exc, OAuthStateError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth callback"
            ) from exc
        if isinstance(exc, OAuthCodeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization failed"
            ) from exc
        raise HTTPException(status_code=500, detail="Authorization failed") from exc
    settings = request.app.state.settings
    response.set_cookie(
        settings.session_cookie_name,
        session_id,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.oauth_state_ttl_seconds,
    )
    return CallbackResponse(user_id=user_id)

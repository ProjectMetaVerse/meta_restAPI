"""Authenticated profile retrieval and normalization."""

from datetime import UTC, datetime
from typing import Any

from meta_api.clients.meta_graph import MetaGraphClient
from meta_api.exceptions.base import (
    AuthenticationError,
    InvalidUpstreamPayloadError,
    MetaUpstreamError,
)
from meta_api.repositories.auth import AuthRepository
from meta_api.schemas.auth import UserProfile


class ProfileService:
    """Fetch only documented profile fields and map them into the public schema."""

    def __init__(self, client: MetaGraphClient, repository: AuthRepository) -> None:
        self.client = client
        self.repository = repository

    async def get_profile(self, session_id: str) -> UserProfile:
        session = await self.repository.get_session(session_id)
        if not session or session.expires_at and session.expires_at <= datetime.now(UTC):
            raise AuthenticationError("Authentication required")
        try:
            payload = await self.client.request(
                "GET",
                "me",
                params={"fields": "id,name,email,first_name,last_name,picture"},
                data={"access_token": session.access_token},
            )
        except MetaUpstreamError as exc:
            raise MetaUpstreamError(
                "Profile service unavailable", status_code=exc.status_code, retryable=exc.retryable
            ) from exc
        user_id = payload.get("id")
        if not isinstance(user_id, str) or not user_id:
            raise InvalidUpstreamPayloadError("Meta returned an invalid profile")
        picture_url: str | None = None
        picture = payload.get("picture")
        if isinstance(picture, dict):
            data = picture.get("data")
            if isinstance(data, dict) and isinstance(data.get("url"), str):
                picture_url = data["url"]
        values: dict[str, Any] = {
            key: payload[key]
            for key in ("name", "email", "first_name", "last_name")
            if isinstance(payload.get(key), str)
        }
        return UserProfile(
            id=user_id, pictureUrl=picture_url, expires_at=session.expires_at, **values
        )

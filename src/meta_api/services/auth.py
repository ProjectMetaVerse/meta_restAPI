"""Meta OAuth orchestration."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit

from meta_api.clients.meta_graph import MetaGraphClient
from meta_api.core.config import Settings
from meta_api.exceptions.base import (
    MetaConfigurationError,
    MetaUpstreamError,
    OAuthCodeError,
    OAuthStateError,
)
from meta_api.repositories.auth import AuthRepository, AuthSession, OAuthState


class AuthService:
    """Handles authorization initiation and callback without exposing credentials."""

    def __init__(
        self, settings: Settings, client: MetaGraphClient, repository: AuthRepository
    ) -> None:
        self.settings = settings
        self.client = client
        self.repository = repository

    def _redirect_uri(self) -> str:
        uri = self.settings.redirect_uri
        if not uri:
            raise MetaConfigurationError("OAuth is not configured")
        parsed = urlsplit(uri)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise MetaConfigurationError("OAuth redirect is not valid")
        if (
            self.settings.allowed_redirect_hosts
            and parsed.netloc not in self.settings.allowed_redirect_hosts
        ):
            raise MetaConfigurationError("OAuth redirect is not allowed")
        return uri

    async def authorization_url(self) -> str:
        redirect_uri = self._redirect_uri()
        state = secrets.token_urlsafe(32)
        await self.repository.save_state(OAuthState(state, datetime.now(UTC)))
        query = urlencode(
            {
                "client_id": self.settings.meta_app_id or "",
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": ",".join(self.settings.meta_permissions),
                "response_type": "code",
            }
        )
        return f"https://www.facebook.com/{self.settings.graph_api_version}/dialog/oauth?{query}"

    async def callback(self, code: str, state: str) -> tuple[str, str]:
        if not code or not state:
            raise OAuthStateError("Invalid OAuth callback")
        stored = await self.repository.consume_state(state)
        if not stored or datetime.now(UTC) - stored.created_at > timedelta(
            seconds=self.settings.oauth_state_ttl_seconds
        ):
            raise OAuthStateError("Invalid OAuth callback")
        try:
            payload = await self.client.request(
                "GET",
                "oauth/access_token",
                params={
                    "client_id": self.settings.meta_app_id or "",
                    "client_secret": (
                        self.settings.meta_app_secret.get_secret_value()
                        if self.settings.meta_app_secret
                        else ""
                    ),
                    "redirect_uri": self._redirect_uri(),
                    "code": code,
                },
            )
        except MetaUpstreamError as exc:
            raise OAuthCodeError("Authorization code exchange failed") from exc
        token = payload.get("access_token")
        user_id = payload.get("user_id")
        if not isinstance(token, str) or not token or not isinstance(user_id, str) or not user_id:
            raise OAuthCodeError("Authorization code exchange failed")
        expires_in = payload.get("expires_in")
        expires_at = None
        if isinstance(expires_in, (int, float)) and expires_in >= 0:
            expires_at = datetime.now(UTC) + timedelta(seconds=float(expires_in))
        session_id = uuid.uuid4().hex
        await self.repository.save_session(AuthSession(session_id, user_id, token, expires_at))
        return session_id, user_id

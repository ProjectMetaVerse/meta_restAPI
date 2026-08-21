"""Persistence boundary for OAuth state and authenticated sessions."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OAuthState:
    value: str
    created_at: datetime


@dataclass(frozen=True)
class AuthSession:
    session_id: str
    user_id: str
    access_token: str
    expires_at: datetime | None


class AuthRepository:
    """Minimal async repository; production deployments can replace this boundary."""

    def __init__(self) -> None:
        self._states: dict[str, OAuthState] = {}
        self._sessions: dict[str, AuthSession] = {}

    async def save_state(self, state: OAuthState) -> None:
        self._states[state.value] = state

    async def consume_state(self, value: str) -> OAuthState | None:
        return self._states.pop(value, None)

    async def save_session(self, session: AuthSession) -> None:
        self._sessions[session.session_id] = session

    async def get_session(self, session_id: str) -> AuthSession | None:
        return self._sessions.get(session_id)

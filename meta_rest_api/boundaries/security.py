"""Security primitives shared by adapters and routers."""

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

SENSITIVE_KEYS = frozenset({"access_token", "refresh_token", "client_secret", "authorization", "code", "state"})


def redact_mapping(values: dict[str, object]) -> dict[str, object]:
    """Return a shallow redacted copy suitable for logs and diagnostics."""
    return {key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else value for key, value in values.items()}


def validate_redirect_uri(candidate: str, allowed: set[str], *, production: bool = True) -> bool:
    """Require an exact allow-list match; production rejects non-HTTPS redirects."""
    parsed = urlparse(candidate)
    if candidate not in allowed or parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return False
    return not production or parsed.scheme == "https"


@dataclass(frozen=True, slots=True)
class OAuthState:
    value: str
    expires_at: datetime
    redirect_uri: str

    def is_valid(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        expiry = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return current < expiry

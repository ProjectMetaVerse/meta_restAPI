"""Domain exceptions exposed by the service layer."""


class MetaAPIError(Exception):
    """Base exception for expected application errors."""


class MetaConfigurationError(MetaAPIError):
    """The Meta integration is not configured safely."""


class MetaUpstreamError(MetaAPIError):
    """A stable, non-sensitive representation of an upstream failure."""

    def __init__(
        self, message: str, *, status_code: int | None = None, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class OAuthStateError(MetaAPIError):
    """OAuth state is missing, expired, or does not match."""


class OAuthCodeError(MetaAPIError):
    """The authorization code could not be exchanged."""


class AuthenticationError(MetaAPIError):
    """The request has no valid authenticated session."""


class InvalidUpstreamPayloadError(MetaAPIError):
    """Meta returned a payload that does not match the contract."""

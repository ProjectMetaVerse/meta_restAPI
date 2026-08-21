"""Typed application exceptions and framework-neutral error serialization."""

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .contracts.v1 import ErrorBody, ErrorFieldDetail, ErrorResponse


@dataclass(slots=True)
class APIError(Exception):
    code: str
    message: str
    status_code: int = 500
    fields: list[ErrorFieldDetail] | None = None

    def __str__(self) -> str:
        return self.message


class ValidationFailure(APIError):
    def __init__(self, message: str = "Request validation failed", fields: list[ErrorFieldDetail] | None = None):
        super().__init__("validation_error", message, 422, fields)


class MetaAPIError(APIError):
    def __init__(self, message: str = "Meta API request failed"):
        super().__init__("meta_api_error", message, 502)


class UpstreamTimeout(APIError):
    def __init__(self, message: str = "Upstream service timed out"):
        super().__init__("upstream_timeout", message, 504)


class RateLimited(APIError):
    def __init__(self, message: str = "Upstream rate limit exceeded"):
        super().__init__("rate_limited", message, 429)


class InvalidOAuthCallback(APIError):
    def __init__(self, message: str = "OAuth callback could not be validated"):
        super().__init__("invalid_oauth_callback", message, 400)


class UnexpectedUpstreamFailure(APIError):
    def __init__(self, message: str = "Unexpected upstream failure"):
        super().__init__("unexpected_upstream_failure", message, 502)


def error_response(error: APIError, request_id: str) -> ErrorResponse:
    """Serialize every public exception into the one stable error envelope."""
    return ErrorResponse(error=ErrorBody(code=error.code, message=error.message, request_id=request_id, fields=error.fields))


def validation_error_response(error: ValidationError, request_id: str) -> ErrorResponse:
    """Convert Pydantic details without exposing input values or secrets."""
    fields = [
        ErrorFieldDetail(field=".".join(str(part) for part in item["loc"]), message=item["msg"])
        for item in error.errors()
    ]
    return error_response(ValidationFailure(fields=fields), request_id)


def map_exception(error: Exception, request_id: str) -> tuple[int, ErrorResponse]:
    """Map known exceptions deterministically; unexpected errors get a generic message."""
    if isinstance(error, ValidationError):
        response = validation_error_response(error, request_id)
        return 422, response
    if isinstance(error, APIError):
        return error.status_code, error_response(error, request_id)
    return 500, error_response(UnexpectedUpstreamFailure(), request_id)

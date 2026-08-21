from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from meta_rest_api.boundaries.security import OAuthState, redact_mapping, validate_redirect_uri
from meta_rest_api.contracts.v1 import (
    AuthCallbackRequest,
    ErrorResponse,
    EventLogRequest,
    EventType,
    PageInfo,
    TokenMetadata,
)
from meta_rest_api.errors import (
    InvalidOAuthCallback,
    ValidationFailure,
    error_response,
    map_exception,
)

NOW = datetime.now(timezone.utc)


def test_auth_callback_contract_rejects_missing_state():
    with pytest.raises(ValidationError):
        AuthCallbackRequest(code="oauth-code", redirect_uri="https://example.test/callback")


def test_event_log_rejects_credentials_in_metadata():
    with pytest.raises(ValidationError, match="credentials"):
        EventLogRequest(
            event_type=EventType.LOGIN,
            occurred_at=NOW,
            idempotency_key="idem-123456",
            metadata={"access_token": "secret"},
        )


def test_public_token_contract_contains_metadata_only():
    token = TokenMetadata(expires_at=NOW, scopes=("public_profile",))
    assert token.model_dump() == {
        "token_type": "bearer",
        "expires_at": NOW,
        "scopes": ("public_profile",),
    }
    assert "access_token" not in token.model_dump_json()


def test_error_serialization_has_stable_envelope_and_request_id():
    response = error_response(InvalidOAuthCallback(), "req-42")
    assert isinstance(response, ErrorResponse)
    assert response.model_dump() == {
        "error": {
            "code": "invalid_oauth_callback",
            "message": "OAuth callback could not be validated",
            "request_id": "req-42",
            "fields": None,
        }
    }


def test_validation_errors_do_not_include_input_values():
    invalid = ValidationError.from_exception_data(
        "AuthCallbackRequest",
        [{"type": "missing", "loc": ("state",), "input": {"code": "super-secret"}}],
    )
    status, response = map_exception(invalid, "corr-7")
    assert status == 422
    assert response.error.request_id == "corr-7"
    assert "super-secret" not in response.model_dump_json()
    assert response.error.fields[0].field == "state"


def test_unexpected_exception_is_generic_and_correlated():
    status, response = map_exception(RuntimeError("token=secret"), "corr-8")
    assert status == 500
    assert response.error.code == "unexpected_upstream_failure"
    assert response.error.request_id == "corr-8"
    assert "secret" not in response.model_dump_json()


def test_redaction_removes_secrets_from_diagnostic_mapping():
    redacted = redact_mapping({"access_token": "abc", "client_secret": "xyz", "user_id": "u1"})
    assert redacted == {"access_token": "[REDACTED]", "client_secret": "[REDACTED]", "user_id": "u1"}


def test_redirect_uri_requires_exact_allow_list_and_https_in_production():
    allowed = {"https://app.example.test/oauth/callback"}
    assert validate_redirect_uri("https://app.example.test/oauth/callback", allowed)
    assert not validate_redirect_uri("https://app.example.test.evil/oauth/callback", allowed)
    assert not validate_redirect_uri("http://app.example.test/oauth/callback", allowed)
    assert validate_redirect_uri("http://localhost:3000/callback", {"http://localhost:3000/callback"}, production=False)


def test_oauth_state_expiry_is_enforced():
    state = OAuthState("state-value", NOW + timedelta(minutes=1), "https://app.example/cb")
    assert state.is_valid(NOW)
    assert not state.is_valid(NOW + timedelta(minutes=2))


def test_pagination_limit_is_bounded():
    assert PageInfo(next_cursor=None, has_more=False, limit=20).limit == 20
    with pytest.raises(ValidationError):
        PageInfo(next_cursor=None, has_more=False, limit=101)

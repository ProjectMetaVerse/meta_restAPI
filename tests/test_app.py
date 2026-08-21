"""Application smoke tests."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from meta_api.core.config import Settings
from meta_api.main import create_app


def test_app_factory_exposes_health_and_docs() -> None:
    """The default non-production app exposes the versioned health route and Swagger UI."""
    app = create_app(Settings(environment="test"))

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        docs_response = client.get("/docs")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "meta-restapi"
    assert docs_response.status_code == 200


def test_production_settings_require_integration_and_security_values() -> None:
    """Production settings fail clearly when mandatory values are missing."""
    with pytest.raises(ValidationError, match="required when environment=production"):
        Settings(environment="production")


def test_production_disables_openapi_endpoints() -> None:
    """Production does not expose interactive API documentation."""
    settings = Settings(
        environment="production",
        meta_app_id="app-id",
        meta_app_secret="app-secret",
        redirect_uri="https://example.com/callback",
        encryption_key="encryption-key",
        signing_key="signing-key",
    )
    app = create_app(settings)

    assert app.openapi_url is None
    assert app.docs_url is None

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="META_",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Meta REST API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"

    meta_app_id: str | None = None
    meta_app_secret: SecretStr | None = None
    redirect_uri: str | None = None
    graph_api_base_url: str = "https://graph.facebook.com"
    graph_api_version: str = "v21.0"
    request_timeout: float = Field(default=10.0, gt=0, le=120)
    max_request_bytes: int = Field(default=1_048_576, gt=0, le=10_485_760)
    trusted_hosts: str = "*"
    cors_origins: str = ""

    database_url: str = "sqlite+aiosqlite:///./meta_api.db"
    encryption_key: SecretStr | None = None
    signing_key: SecretStr | None = None
    event_read_token: SecretStr | None = None

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return normalized

    @field_validator("redirect_uri")
    @classmethod
    def validate_redirect_uri(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
        ):
            raise ValueError("redirect_uri must be an absolute HTTPS URI without credentials")
        return value

    @field_validator(
        "meta_app_id", "meta_app_secret", "redirect_uri", "encryption_key", "signing_key"
    )
    @classmethod
    def require_production_values(cls, value: object, info: ValidationInfo) -> object:
        if info.data.get("environment") == "production" and not value:
            raise ValueError(f"{info.field_name} is required when environment=production")
        return value

    def trusted_host_list(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()] or ["*"]

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable-by-convention settings instance."""
    return Settings()

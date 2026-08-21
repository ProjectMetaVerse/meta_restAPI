"""FastAPI application factory and local entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from meta_api.api.v1.auth import router as auth_router
from meta_api.api.v1.health import router as health_router
from meta_api.api.v1.profile import router as profile_router
from meta_api.clients.meta_graph import MetaGraphClient
from meta_api.core.config import Settings, get_settings
from meta_api.core.logging import configure_logging
from meta_api.repositories.auth import AuthRepository
from meta_api.services.auth import AuthService
from meta_api.services.profile import ProfileService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a FastAPI application instance."""
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.log_level)
    docs_enabled = runtime_settings.environment != "production"

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("application_started", extra={"environment": runtime_settings.environment})
        yield

    app = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        description="Asynchronous API for Meta platform integrations.",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    repository = AuthRepository()
    client = MetaGraphClient(
        runtime_settings.graph_api_base_url,
        runtime_settings.graph_api_version,
        connect_timeout=runtime_settings.graph_connect_timeout,
        read_timeout=runtime_settings.graph_read_timeout,
        max_retries=runtime_settings.graph_max_retries,
    )
    app.state.settings = runtime_settings
    app.state.auth_repository = repository
    app.state.auth_service = AuthService(runtime_settings, client, repository)
    app.state.profile_service = ProfileService(client, repository)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(profile_router, prefix="/api/v1")
    return app


app = create_app()


def run() -> None:
    """Start the development server with Uvicorn."""
    uvicorn.run("meta_api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()

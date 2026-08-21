"""FastAPI application factory and local entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from meta_api.api.v1.events import router as events_router
from meta_api.api.v1.health import router as health_router
from meta_api.core.config import Settings, get_settings
from meta_api.core.logging import configure_logging
from meta_api.repositories.events import SQLiteEventRepository

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a FastAPI application instance."""
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.log_level)
    docs_enabled = runtime_settings.environment != "production"
    repository = SQLiteEventRepository(runtime_settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await repository.initialize()
        app.state.event_repository = repository
        app.state.settings = runtime_settings
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
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    return app


app = create_app()


def run() -> None:
    """Start the development server with Uvicorn."""
    uvicorn.run("meta_api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()

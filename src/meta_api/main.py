from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from meta_api.api.v1.events import router as events_router
from meta_api.api.v1.health import router as health_router
from meta_api.core.config import Settings, get_settings
from meta_api.core.logging import configure_logging, request_id_context
from meta_api.repositories.events import SQLiteEventRepository

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        requested = request.headers.get("X-Request-ID", "").strip()
        correlation_id = requested[:128] if requested else str(uuid4())
        token = request_id_context.set(correlation_id)
        try:
            if (
                request.headers.get("content-length")
                and int(request.headers["content-length"])
                > request.app.state.settings.max_request_bytes
            ):
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    {"detail": "request body too large"},
                    status_code=413,
                    headers={"X-Request-ID": correlation_id},
                )
            response = await call_next(request)
            response.headers["X-Request-ID"] = correlation_id
            return response
        finally:
            request_id_context.reset(token)


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.log_level)
    docs_enabled = runtime_settings.environment != "production"
    repository = SQLiteEventRepository(runtime_settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = False
        try:
            await repository.initialize()
            app.state.event_repository = repository
            app.state.settings = runtime_settings
            app.state.ready = True
            logger.info("application_started", extra={"environment": runtime_settings.environment})
            yield
        finally:
            await repository.close()
            app.state.ready = False
            logger.info("application_stopped")

    app = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        description="Asynchronous API for Meta platform integrations.",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=runtime_settings.trusted_host_list())
    if runtime_settings.cors_origin_list():
        app.add_middleware(
            CORSMiddleware,
            allow_origins=runtime_settings.cors_origin_list(),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    return app


app = create_app()


def run() -> None:
    uvicorn.run("meta_api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()

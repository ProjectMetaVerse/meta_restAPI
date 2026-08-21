# Meta REST API

An asynchronous Python 3.11+ service built with FastAPI for Meta platform integrations. The repository follows a `src` layout and keeps configuration, API routing, external clients, services, repositories, models, schemas, and exceptions separated for incremental feature development.

## Local setup

Create and activate a virtual environment, install the development dependencies, and copy the example environment file:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
make install
cp .env.example .env
```

The example file contains placeholders only. Replace them with development credentials when exercising Meta integrations. Production startup validates the Meta application credentials, redirect URI, encryption key, and signing key instead of silently accepting unsafe defaults.

## Run the service

```bash
make run
```

The service is available at `http://localhost:8000`. In non-production environments, interactive Swagger UI is available at `/docs`, ReDoc at `/redoc`, and the OpenAPI document at `/openapi.json`. The versioned liveness endpoint is `GET /api/v1/health`; `GET /api/v1/ready` reports dependency readiness and returns `503` until the event repository has initialized.

Every response includes `X-Request-ID`. A caller-provided value is bounded to 128 characters; otherwise the service generates a UUID and carries it into structured logs. Event reads require `META_EVENT_READ_TOKEN` when configured. Persistence failures expose only a stable `event persistence unavailable` response while detailed exceptions remain in server logs with sensitive fields filtered.

Operational controls include `META_MAX_REQUEST_BYTES` (default 1 MiB, maximum 10 MiB), `META_TRUSTED_HOSTS` (comma-separated hostnames), and `META_CORS_ORIGINS` (comma-separated explicit origins). Production requires HTTPS redirect URIs without embedded credentials, and also validates the existing Meta credentials, encryption key, and signing key. SQLite writes serialize the full idempotency transaction, so concurrent retries resolve deterministically to one stored event or a conflict.

A direct entry point is also available:

```bash
python -m meta_api.main
```

## Project layout

```text
src/meta_api/
├── api/v1/          # Versioned HTTP routers
├── clients/         # Typed async integrations, including Graph API boundary
├── core/            # Settings and structured logging
├── exceptions/      # Application exception hierarchy
├── models/          # Persistence/domain models
├── repositories/    # Async repository contracts and implementations
├── schemas/         # Request and response schemas
├── services/        # Application use cases
└── main.py          # FastAPI application factory and Uvicorn entry point
```

## Quality checks

The project uses Ruff for import sorting, linting, and formatting; mypy in strict mode for static typing; pytest with pytest-asyncio for asynchronous tests; and coverage for test reporting.

```bash
make format
make lint
make typecheck
make test
make coverage
# Or run the complete local gate:
make check
```

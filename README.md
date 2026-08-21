# Meta REST API

Meta REST API is an asynchronous Python 3.11+ service built with FastAPI. It provides a versioned health endpoint and a durable, idempotent event-ingestion API behind a `src` layout. Meta Graph API credentials and redirect settings are configuration inputs for the integration boundary; the current public routes are documented below and in the generated OpenAPI document.

## Quickstart

### Prerequisites

Use Python 3.11 or newer. The supported development workflow uses a virtual environment and the package's development extra, which installs the exact tool families used by continuous integration: Ruff, mypy, pytest, pytest-asyncio, and coverage.

```bash
git clone https://github.com/ProjectMetaVerse/meta_restAPI.git
cd meta_restAPI
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
make install
cp .env.example .env
```

The default development configuration uses a local SQLite database. No real Meta credentials are required to run the service or execute the test suite. Keep `.env` local; it is ignored by Git.

### Configuration

Settings are read from environment variables with the `META_` prefix. The complete, copyable list is in [.env.example](.env.example).

| Variable | Development value or meaning | Production expectation |
| --- | --- | --- |
| `META_ENVIRONMENT` | `development` | Set to `production` to enable production validation. |
| `META_LOG_LEVEL` | `INFO` | Choose the smallest useful level and centralize structured logs. |
| `META_META_APP_ID` | Placeholder | The Meta App ID issued by the Meta developer dashboard. |
| `META_META_APP_SECRET` | Placeholder | Store as a deployment secret; never commit or log it. |
| `META_REDIRECT_URI` | `http://localhost:8000/api/v1/auth/callback` | Use the exact HTTPS callback registered in Meta. |
| `META_GRAPH_API_BASE_URL` | `https://graph.facebook.com` | Keep the trusted Meta Graph API origin unless an approved proxy is used. |
| `META_GRAPH_API_VERSION` | `v21.0` | Pin and upgrade deliberately after compatibility testing. |
| `META_REQUEST_TIMEOUT` | `10` seconds | Keep finite and tune for the deployment's SLO. |
| `META_DATABASE_URL` | `sqlite+aiosqlite:///./meta_api.db` | Use an encrypted, access-controlled production database. |
| `META_ENCRYPTION_KEY` | Placeholder | Generate and store a high-entropy secret in the deployment secret manager. |
| `META_SIGNING_KEY` | Placeholder | Generate and store separately from the encryption key. |
| `META_EVENT_READ_TOKEN` | Empty | Optional bearer token protecting event retrieval; ingestion is independent. |

For local development, create a non-production `.env` with placeholder Meta values and leave `META_ENVIRONMENT=development`. Production startup validates the Meta application credentials, redirect URI, encryption key, and signing key rather than silently accepting unsafe defaults.

### Meta app and OAuth configuration

Create or select the Meta app in the Meta developer dashboard, add the products and permissions required by the integration, and copy the App ID and App Secret into the deployment's secret store. In the app's OAuth or Facebook Login settings, add the value of `META_REDIRECT_URI` to the **Valid OAuth Redirect URIs** list. Matching is exact: scheme, hostname, port, path, and relevant trailing slash behavior must agree. Use a separate Meta app and callback for local, staging, and production environments.

The configured callback is the integration contract for the Meta client layer. This repository currently exposes health and event routes only; it does not claim a public `/api/v1/auth/callback` route yet. Do not advertise or depend on an OAuth callback endpoint until the corresponding authentication feature is implemented. When that feature is added, its route, state/nonce validation, token exchange, and required Meta permissions must be added to the OpenAPI schema and this guide together.

### Start the service

```bash
. .venv/bin/activate
make run
```

The server listens on `http://localhost:8000`. The equivalent direct command is:

```bash
python -m uvicorn meta_api.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API documentation is available at [`/docs`](http://localhost:8000/docs), ReDoc at [`/redoc`](http://localhost:8000/redoc), and the generated OpenAPI JSON at [`/openapi.json`](http://localhost:8000/openapi.json). The liveness route is `GET /api/v1/health`.

## API usage

### Health check

```bash
curl --fail-with-body http://localhost:8000/api/v1/health
```

A successful response has the shape `{"status":"ok","service":"meta-restapi","timestamp":"..."}`.

### Ingest an event

The request schema requires `idempotency_key`, `name`, and `source`; `payload` is an optional JSON object limited to 64 KiB. The endpoint returns `202 Accepted` for both a new event and an idempotent replay.

```bash
curl --fail-with-body -X POST http://localhost:8000/api/v1/events \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: checkout-2026-0001' \
  -d '{
    "idempotency_key": "checkout-2026-0001",
    "name": "checkout.completed",
    "source": "orders-service",
    "actor_ref": "user-123",
    "session_ref": "session-456",
    "payload": {"order_id": "order-789", "total": 42.50},
    "occurred_at": "2026-08-21T12:00:00Z"
  }'
```

The response is an object containing `event` and `replayed`. Repeating the same `idempotency_key` with the same logical event returns the original event with `replayed: true`; reusing the key for a different event returns `409 Conflict`. This behavior makes safe client retries possible without creating duplicate logical records. Send credentials, access tokens, passwords, or unredacted personal data only through a future dedicated secret-aware integration, never in event payload metadata.

### Retrieve events

Retrieval is newest-first and cursor-paginated. The default page size is 50 and the maximum is 100. Set `META_EVENT_READ_TOKEN` to require a bearer token for both listing and single-event retrieval; ingestion remains independent.

```bash
curl --fail-with-body \
  -H 'Authorization: Bearer replace-with-your-read-token' \
  'http://localhost:8000/api/v1/events?limit=50'

curl --fail-with-body \
  -H 'Authorization: Bearer replace-with-your-read-token' \
  http://localhost:8000/api/v1/events/EVENT_ID
```

Use the `next_cursor` value returned by a page as the `before` query parameter for the next page. If no read token is configured, the authorization header is optional in development. The request and response models, field limits, status codes, and examples above are generated from the same Pydantic models that produce `/openapi.json`.

## Testing and quality gates

Run the same essential gates locally that run for every pull request. `make check` formats files in place, then runs linting, strict type checking, and tests. The non-mutating CI-equivalent sequence is useful before committing:

```bash
ruff format --check .
ruff check .
mypy src
coverage run -m pytest --junitxml=test-results.xml
coverage report --fail-under=80 --show-missing
coverage xml
```

The focused commands remain available:

```bash
make format
make lint
make typecheck
make test
make coverage
make check
```

Tests use temporary SQLite databases and do not require Meta credentials, network access, or a running server. The GitHub Actions workflow runs on Python 3.11 and 3.12, publishes JUnit and coverage artifacts, and keeps secrets out of logs.

## Security and production operations

Treat every secret as a deployment concern. Store `META_META_APP_SECRET`, `META_ENCRYPTION_KEY`, `META_SIGNING_KEY`, database credentials, and `META_EVENT_READ_TOKEN` in the hosting platform's encrypted secret manager. Do not put them in Git, issue comments, CI output, request payloads, or exception messages. Rotate them with a planned migration and invalidate compromised tokens promptly.

Terminate TLS at a trusted load balancer or configure HTTPS directly; production clients must never send OAuth credentials or bearer tokens over plaintext HTTP. Restrict CORS to known application origins rather than using a wildcard, and keep OAuth redirect URIs exact and environment-specific. Apply authentication and least-privilege Meta permissions when the OAuth routes are introduced. Add edge or gateway rate limiting for event ingestion and retrieval, bound request sizes, and retain finite client and upstream timeouts.

Application logs are structured and intentionally exclude payloads, credentials, authorization headers, and secret settings. In production, ship logs to an access-controlled system with retention and redaction policies, alert on repeated authorization failures and persistence errors, and avoid enabling debug logging for untrusted traffic. Protect the database with encryption at rest, restricted network access, backups, deletion/retention policies, and a tested restore procedure. Run the service as a non-root user and review dependency updates through CI.

## Repository layout

```text
src/meta_api/
├── api/v1/          # Versioned HTTP routers
├── clients/         # Typed async integration boundaries
├── core/            # Configuration and logging
├── exceptions/      # Application exception hierarchy
├── models/          # Domain and persistence models
├── repositories/    # Async repository contracts and implementations
├── schemas/         # Request and response Pydantic schemas
├── services/        # Application use cases
└── main.py          # FastAPI application factory and Uvicorn entry point
```

See [docs/events.md](docs/events.md) for persistence, pagination, retention, and event-log details. See [CONTRIBUTING.md](CONTRIBUTING.md) for the pull-request workflow.

## References

[1]: https://fastapi.tiangolo.com/ FastAPI documentation
[2]: https://docs.github.com/en/actions GitHub Actions documentation
[3]: https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow Meta OAuth documentation

# Release Readiness Checklist

This document records the validation scope for `feature/t8-release-validation`. It is intended to be reviewed before merging to `main` and reused during deployment. The validation uses only the documented development/test configuration and mocked Meta transport; it does not require live Meta credentials.

## Validation summary

| Area | Command or verification | Expected result | Status |
|---|---|---|---|
| Clean install | `python3.11 -m venv .venv`; `. .venv/bin/activate`; `make install` | Editable package and development dependencies install successfully | PASS |
| Formatting | `make format` | Ruff reports files unchanged or formats only intentional changes | PASS |
| Linting | `make lint` | Ruff reports no violations | PASS |
| Static typing | `make typecheck` | Mypy strict mode reports no issues | PASS |
| Unit and integration tests | `make test` | All tests pass with strict pytest configuration | PASS |
| Coverage | `make coverage` | Branch coverage meets the configured 85% threshold | PASS |
| Dependency consistency | `python -m pip check` | No incompatible installed dependencies | PASS |
| Python syntax | `python -m compileall -q src tests` | All source and test modules compile | PASS |
| Runtime boot and health | `uvicorn meta_api.main:app --host 127.0.0.1 --port 8000`; `GET /api/v1/health` | HTTP 200 and `status=ok` | PASS |
| API documentation | `GET /docs`, `GET /redoc`, `GET /openapi.json` in non-production | HTTP 200 and valid OpenAPI JSON | PASS |
| Production safety | Instantiate `Settings(environment="production")` without credentials | ValidationError; no unsafe startup defaults | PASS |
| Meta boundary | `GraphAPIClient` with `httpx.MockTransport` | Representative request is testable without network access | PASS |
| Example configuration | Inspect `.env.example` and run the secret-safety test | Placeholders only; no credentials or tokens | PASS |
| CI alignment | Inspect `.github/workflows/ci.yml` | Workflow runs the same install, format, lint, type, test, coverage, and dependency checks | PASS |

The repository has no dependency lock file and no database migration framework at this revision. Dependency versions are therefore bounded by `pyproject.toml`, and the current SQLite event repository initializes its schema at application startup. These are explicit operational limitations rather than undocumented assumptions.

## Deployment prerequisites

Before deployment, set the `META_` environment variables listed below through the deployment platform’s secret/configuration store. Do not commit `.env`, database files, access tokens, or private keys. The `production` environment requires `META_META_APP_ID`, `META_META_APP_SECRET`, `META_REDIRECT_URI`, `META_ENCRYPTION_KEY`, and `META_SIGNING_KEY`; startup must fail closed if any is missing. Configure `META_DATABASE_URL` to a persistent database location and set an appropriate `META_EVENT_READ_TOKEN` if event retrieval is exposed beyond a trusted network.

| Variable | Required in production | Purpose |
|---|---:|---|
| `META_ENVIRONMENT` | Yes | Set to `production` to activate fail-safe validation and disable interactive API documentation |
| `META_META_APP_ID` | Yes | Meta application identifier |
| `META_META_APP_SECRET` | Yes | Meta application secret; store as a secret |
| `META_REDIRECT_URI` | Yes | Exact OAuth callback URL registered with Meta |
| `META_GRAPH_API_BASE_URL` | No | Graph API host; default is `https://graph.facebook.com` |
| `META_GRAPH_API_VERSION` | No | Graph API version; default is `v21.0` |
| `META_REQUEST_TIMEOUT` | No | Positive upstream timeout in seconds |
| `META_DATABASE_URL` | Yes operationally | Persistent event storage location |
| `META_ENCRYPTION_KEY` | Yes | Application encryption key; store as a secret |
| `META_SIGNING_KEY` | Yes | Application signing key; store as a secret |
| `META_EVENT_READ_TOKEN` | Recommended | Bearer token protecting event reads |

## Migration and data handling

There are no versioned migrations in this repository. The current SQLite repository creates the `events` table and indexes during application lifespan initialization. For a new deployment, provision the persistent database path or managed database first, start the application once, and verify the health endpoint and event API. For future schema changes, introduce a versioned migration mechanism before applying incompatible changes; do not rely on deleting the production database.

Before deployment, back up the event database according to the hosting platform’s persistent-volume procedure. Confirm that the backup can be restored to a staging instance and that the restored instance passes the health and event-read checks. Event payloads may contain sensitive business data, so backups and logs require the same access controls and retention policy as production.

## Rollback procedure

If deployment fails health checks or introduces a regression, stop traffic to the new revision and roll back to the last known-good application image and configuration. Preserve the failed revision’s logs and database backup for diagnosis. Because this revision has no versioned migrations, rollback is safe only when no incompatible schema change has been applied; if a future release adds migrations, document forward-compatible migrations and an explicit downgrade or restore plan before merge. Re-run `/api/v1/health`, `/docs`/`/openapi.json` in a non-production validation environment, and a representative authenticated event-read request after rollback.

## Manual Meta App Dashboard configuration

The deployment operator must configure the Meta App Dashboard outside this repository. Select the required products and permissions for the integration, register the exact value of `META_REDIRECT_URI` under the OAuth redirect allowlist, and ensure the application mode, privacy policy URL, data deletion URL, domain allowlist, and any required webhook subscriptions match the deployed environment. Store the resulting app ID and secret only in the deployment secret store. Test OAuth and Graph API permissions in a non-production Meta app before enabling production traffic.

## Known limitations and merge checklist

The Graph client currently provides a typed HTTP boundary but does not itself implement token exchange, token refresh, retry policy, or webhook verification. Those capabilities must not be inferred from the presence of the client class. The API documentation is intentionally disabled in production, and the event repository is SQLite-based with no built-in retention job. Operators must provide persistent storage, backup, retention, encryption at rest, and access control.

Before merge, reviewers should confirm that the CI workflow is green, no secret-bearing files are staged, the environment variable changes are reflected in `.env.example`, the persistent database path is suitable for the target runtime, and the Meta Dashboard configuration has been prepared. Before release, run the complete checklist above against the release commit and retain the generated test and coverage reports as CI artifacts.

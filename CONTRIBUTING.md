# Contributing to Meta REST API

Thank you for improving Meta REST API. Contributions should preserve the service's typed, asynchronous architecture, its security boundaries, and its idempotent event behavior. Read the [README](README.md) first, especially the configuration, API, and security sections.

## Development workflow

Create a branch from an up-to-date `main` branch. Use a descriptive branch name such as `feature/event-replay`, `fix/cursor-validation`, `docs/quickstart`, or `chore/dependency-refresh`; avoid committing directly to `main`.

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
git checkout -b feature/short-description
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
make install
```

Keep changes focused and update documentation, OpenAPI-visible models, and tests together. Do not add real Meta credentials, database files, access tokens, or generated local artifacts to a commit.

## Tests and review requirements

Before opening a pull request, run the same non-mutating checks as CI:

```bash
ruff format --check .
ruff check .
mypy src
coverage run -m pytest --junitxml=test-results.xml
coverage report --fail-under=80 --show-missing
coverage xml
```

A pull request must pass the GitHub Actions matrix on Python 3.11 and 3.12, include regression tests for behavior changes, and keep coverage at or above 80 percent. Reviewers expect clear scope, a useful commit history, updated API or operational documentation where applicable, and no secrets in source, fixtures, logs, or examples. At least one maintainer review is required before merge, and unresolved review comments must be addressed or explicitly documented.

Tests should be deterministic and isolated. Use temporary paths or in-memory test fixtures rather than shared developer databases. For event changes, cover new ingestion, idempotent replay, conflicting reuse of an idempotency key, validation failures, pagination, authorization, and log redaction as relevant.

## Database and migration expectations

Any persistence schema or repository change must include a migration plan before merge. Describe backward compatibility, deployment ordering, rollback behavior, data backfill or retention impact, and how the change will be verified against a copy of representative data. Never rely on an implicit destructive schema reset in production. If a migration tool is introduced, document its exact local and deployment commands and add the migration files to version control.

## Pull requests and commits

Use a concise imperative commit subject, such as `Add pull request quality gates` or `Validate event cursor input`. Pull requests should explain the problem, summarize the implementation, identify configuration or migration impact, and list the commands that passed locally. Include example request/response changes when an API contract changes. Keep generated coverage output and local `.env` files untracked.

Maintainers may request a follow-up issue for unrelated cleanup rather than expanding the current pull request. After approval and green CI, merge using the repository's configured merge strategy; release notes should call out security, API, configuration, and migration changes that affect operators.

# API Contracts and Security Architecture

## Scope and versioning

The public payloads live in `meta_rest_api.contracts.v1`. The `v1` namespace is an explicit compatibility boundary: additive fields may be introduced only with a documented compatibility decision, while changing field meaning, removing fields, or changing error codes requires a new version. Routers should expose these models and must not return raw Meta Graph payloads.

## Trust boundaries

| Boundary | Trusted responsibility | Required control |
|---|---|---|
| Browser/client → API | Untrusted input and bearer/session context | Pydantic validation, request-ID propagation, rate limiting, no secret echo |
| API → OAuth provider | External authorization and token exchange | Exact allow-listed redirect URI, one-time state, short state TTL, HTTPS in production |
| API → Meta Graph | External upstream dependency | Dedicated `MetaGraphClient`, pinned Graph API version in the adapter, timeouts, retry policy, error translation |
| API → token/session store | Sensitive server-side persistence | Encrypt at rest, least-privilege access, expiry metadata, revoke support, never expose raw token |
| API → event repository | Application persistence | Unique `(user_id, idempotency_key)` constraint and deterministic replay response |
| API → logs/telemetry | Potentially durable diagnostic sink | Redact tokens, OAuth code/state, client secrets, and authorization headers before serialization |

## OAuth and session security

The initiation adapter generates cryptographically random state, binds it to the exact redirect URI and an expiry, and stores it server-side or in an authenticated, encrypted session. The callback must require a matching, unexpired, single-use state and exact redirect URI. Provider error callbacks are mapped to `invalid_oauth_callback` without returning provider internals.

Access tokens are storage-only credentials. Public responses contain `TokenMetadata` (type, expiry, and scopes) but never raw token values. Tokens must be encrypted at rest, excluded from logs, traces, analytics, exception messages, and client payloads, and revoked or deleted when a session ends. Expiry is represented as an absolute timezone-aware `expires_at` timestamp.

## Meta Graph client boundary

Only the adapter implementing `MetaGraphClient` may know Meta URLs, Graph API versions, provider-specific field names, token exchange details, and upstream error codes. Application services depend on the protocol and translate provider failures to the typed exception taxonomy. The required permission set must be reviewed against the smallest product need; a baseline profile integration generally requests only the identity/profile permissions approved for the deployed Meta app, and no permission is granted implicitly by this contract.

The adapter must pin a Graph API version through configuration, set bounded connect/read timeouts, and classify upstream timeouts, rate limits, and malformed responses. API version upgrades are deployment changes and must be tested against contract fixtures before rollout.

## Event logging and persistence

Event creation accepts an application-generated idempotency key. Repeating the same key for the same user must return the original event and must not create a duplicate. A repository implementation should enforce this invariant with a unique database constraint; the protocol intentionally leaves the persistence technology unspecified.

## Error envelope

Every public failure is serialized as `{ "error": { "code", "message", "request_id", "fields" } }`. Codes are stable machine-readable identifiers. Messages are safe for clients and must not expose access tokens, authorization codes, SQL, upstream headers, or stack traces. `request_id` is generated or propagated at the edge and is included in structured logs and responses for support correlation.

## Environment posture

Local development may use HTTP loopback redirects and in-memory fakes, but must still exercise state validation and redaction. Production requires HTTPS, managed secret storage, encrypted token persistence, restrictive CORS, secure cookies where sessions are used, log scrubbing, dependency timeouts, and operational alerting for repeated upstream failures. Test fixtures must use synthetic credentials only.

# Laravel website integration gateway

The adapter lives outside Laravel's web document directory and exposes `/internal/api/v1/demo-command-center/*` behind service authentication, private networking where available, request timestamp/replay checks, content limits, rate limits, and audit logging.

Required endpoints:

| Method/path | Scope | Result |
|---|---|---|
| `GET /tutors/candidates` | `demo:tutors:read` | Normalized tutor/course/review/location summary and source version; no private contact |
| `POST /tutors/contact-resolve` | `demo:tutor-contact:read` | Purpose-bound authoritative email reference/value for server delivery only |
| `GET /plans/{id}/quote` | `demo:plans:read` | Plan/version, amount minor, currency, eligibility and expiry |
| `POST /subscriptions/activations` | `demo:subscription:write` | Idempotent activation ledger reference and outbox event |
| `GET /identities/resolve` | `demo:identity:read` | Scoped exact mappings; ambiguous matches are explicit |
| `POST /admin/exchange` | `demo:admin:access` | Short-lived tenant/region/scopes claims derived from Laravel auth |
| `POST /demo-leads/{id}/handoff` | `demo:lead:write` | Correlates captured lead and writes Laravel outbox |

Responses carry schema/source version, generated time, tenant, correlation, and pagination. The gateway normalizes both tutor-course representations and returns availability as `unknown` until an authoritative model exists. Mutations use a dedicated ledger with unique client idempotency key and commit an outbox row in the same MySQL transaction.

CSRF remains enabled for browser calls. Service endpoints are not session-authenticated and use a distinct guard. The Python service never receives Laravel DB credentials. Timeout, retries, and circuit-breaker behavior are bounded; writes reconcile before retry.

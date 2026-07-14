# NXTutors Laravel integration gateway blueprint

This package belongs in the Laravel project root or a private Composer package, never in the website's nested `public/` document directory. It is a reviewed blueprint; copying it does not activate production access.

The gateway exposes versioned internal routes for normalized tutor data, authoritative plan quotes, identity resolution, purpose-bound phone recipient references, and exactly-once subscription activation. Browser sessions/CSRF are not used for service calls. Deploy behind private routing where possible and verify short-lived JWT/HMAC, audience, key ID, timestamp, nonce/replay, content size, tenant/scope, idempotency, and rate limits.

`demo_integration_outbox` and `demo_subscription_activations` commit with a website mutation. The Demo service never receives MySQL credentials. Before enabling, add controllers/resources/repositories, bind real auth verification, migrate in a reviewed window, backfill no data automatically, and run contract tests against the current legacy schema.

The Laravel website keeps the real MySQL settings in its own `.env`. Use this package's `.env.example` as a shape-only checklist for `DB_CONNECTION=mysql`, `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD`, optional `DB_SSL_CA`, and reviewed `DEMO_COMMAND_CENTER_TABLE_*` mappings. Never paste live `DB_PASSWORD`, HMAC secrets, or audit keys into this repository.

Teacher-first scheduling resolves `register.phone` only through `/tutors/{tutor}/phone-resolve` with `demo:tutor-phone:read`; student session-link delivery resolves through `/profiles/{register}/phone-resolve` with `demo:profile-phone:read`. Both endpoints return an opaque `recipient_ref` plus a masked phone for operator audit and do not expose the raw phone number.

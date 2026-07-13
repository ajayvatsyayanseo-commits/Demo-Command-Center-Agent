# NXTutors Laravel integration gateway blueprint

This package belongs in the Laravel project root or a private Composer package, never in the website's nested `public/` document directory. It is a reviewed blueprint; copying it does not activate production access.

The gateway exposes versioned internal routes for normalized tutor data, authoritative plan quotes, identity resolution, and exactly-once subscription activation. Browser sessions/CSRF are not used for service calls. Deploy behind private routing where possible and verify short-lived JWT/HMAC, audience, key ID, timestamp, nonce/replay, content size, tenant/scope, idempotency, and rate limits.

`demo_integration_outbox` and `demo_subscription_activations` commit with a website mutation. The Demo service never receives MySQL credentials. Before enabling, add controllers/resources/repositories, bind real auth verification, migrate in a reviewed window, backfill no data automatically, and run contract tests against the current legacy schema.

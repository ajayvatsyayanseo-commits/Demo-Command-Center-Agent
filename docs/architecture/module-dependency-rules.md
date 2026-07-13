# Module dependency rules

Allowed direction:

```text
transport/workers/CLI -> application -> domain
infrastructure/integrations -> application ports -> domain types
```

Rules:

1. Domain imports only standard-library types and other explicitly allowed domain types.
2. Application code coordinates domain objects and ports; it does not import concrete adapters.
3. FastAPI, SQLAlchemy, boto3, redis, httpx, Google, Cashfree, Meta, and OpenAI types stay in adapters/transport.
4. Capability modules communicate through application contracts/events, never another module's repositories.
5. A side effect starts only after command validation, authorization, policy checks, and idempotency reservation.
6. LLM results are typed evidence/drafts and cannot invoke a port directly.
7. `tests/fakes` is importable only from tests and explicit local bootstrap code must use its own local adapters.
8. Shared code needs a named owner; no generic `utils.py`, `helpers.py`, or service-locator imports.

Architecture tests scan imports, production-to-fake dependencies, route authentication, event invariants, and state registration.

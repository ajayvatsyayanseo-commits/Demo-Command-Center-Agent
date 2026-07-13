# Contributing

Use Python 3.12, focused modules, typed ports, and small reviewed changes. Add or update contracts before changing an integration. Include unit, architecture, security, and contract tests proportional to risk.

Run:

```bash
make format
make check
```

Do not commit generated credentials, local `.env` files, provider payloads, or analytics containing raw PII. Database migrations are forward-only after production release and require a rollback/compatibility note.

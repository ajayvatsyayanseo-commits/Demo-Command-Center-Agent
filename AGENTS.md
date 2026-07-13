# Agent working agreement

This repository is the architecture scaffold for the NXTutors Demo Command Center Agent.

- Preserve the modular-monolith and hexagonal dependency direction documented in `docs/architecture/module-dependency-rules.md`.
- Domain code must not import FastAPI, SQLAlchemy, provider SDKs, or test fakes.
- The Laravel/MySQL website remains authoritative for profiles, tutors, plans, orders, and subscriptions. Mutate it only through the versioned website gateway.
- Lead Intake is the canonical public Meta ingress and outbound WhatsApp sender. Do not add a second active Meta responder.
- Every external event and side effect requires an idempotency key and durable inbox/outbox record.
- LLM output is advisory, typed, redacted, and policy checked. It never confirms availability, payment, discounts, or lifecycle state.
- Keep real credentials out of files and logs. Production must reject fake/local adapters.
- Do not create Git commits or change repository history while completing the implementation phase.
- Run `make check` and update `docs/discovery/codex-final-report.md` with evidence when behavior or contracts change.

See `docs/architecture/` and accepted ADRs before implementing a module.

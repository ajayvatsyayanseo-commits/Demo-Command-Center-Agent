# ADR-003: Database and data ownership

- Status: Accepted
- Date: 2026-07-13

## Context

Laravel/MySQL owns legacy profiles/tutors/plans/subscriptions. The demo lifecycle needs stronger normalization, concurrency, event, and analytics boundaries.

## Decision

Demo Command Center owns Aurora PostgreSQL tables listed in the canonical data model. Laravel/MySQL remains authoritative for existing website domains. Integration uses an authenticated versioned Laravel gateway and transactional outbox. Python performs no arbitrary MySQL writes and no cross-database transactions.

## Consequences

Each service has clear invariants and migration ownership. Cross-system operations become idempotent sagas with reconciliation. A read-only direct adapter is not approved; it would require evidence, least-privilege credentials, compatibility tests, and a replacement ADR.

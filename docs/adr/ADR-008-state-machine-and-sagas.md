# ADR-008: State machine and sagas

- Status: Accepted
- Date: 2026-07-13

## Context

Demo scheduling/payment spans databases and providers without distributed transactions. Implicit status changes are difficult to retry or audit.

## Decision

Use the explicit registered lifecycle state machine plus scheduling/payment sagas. Commands declare prior state, actor, guards, requested effects, and compensation. Orthogonal confirmation/delivery/calendar/payment details use typed records. Optimistic case versions and transition idempotency serialize decisions.

## Consequences

Every transition is explainable and replay-safe. New states/commands require registry, documentation, migration compatibility, and tests. Compensations restore business safety rather than pretending remote atomicity; uncertain provider outcomes reconcile before retry.

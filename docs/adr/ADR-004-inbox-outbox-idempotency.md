# ADR-004: Inbox, outbox, and idempotency

- Status: Accepted
- Date: 2026-07-13

## Context

HTTP, SQS, Meta, Calendar, Cashfree, and agent events are at-least-once. A database commit cannot atomically include a provider call.

## Decision

Every inbound event is inserted into a unique durable inbox before acknowledgement. State and outbox rows commit together. Dispatchers publish/execute with stable operation keys, bounded leases/retries, and reconciliation. Side-effect results are persisted before completion. Redis may optimize but is not the dedupe source of truth.

## Consequences

Duplicate delivery is normal and safe. Consumers must define idempotency scope, request hash, retention, and response replay. Operators need DLQ/redrive and outbox-age tooling. Exactly-once business effect is achieved through durable uniqueness and idempotent reconciliation, not transport promises.

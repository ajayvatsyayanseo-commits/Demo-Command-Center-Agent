# ADR-009: Cache and locking

- Status: Accepted
- Date: 2026-07-13

## Context

Hot conversation/policy/provider state benefits from Redis, but cache loss and lease expiry cannot permit duplicate bookings or payments.

## Decision

Redis holds caches, throttles, circuit state, and short leases under versioned hashed keys. PostgreSQL constraints, optimistic versions, range exclusion, inbox/idempotency, and transaction locks establish truth. A Redis lease includes owner/fencing information; release is compare-and-delete. TTLs come from configuration/policy.

## Consequences

Redis failure causes conservative degraded performance, not invariant loss. Cache entries need explicit invalidation/versioning. Locks cannot cover provider calls without durable operation records. Metrics track misses, contention, lease expiry, and fallback.

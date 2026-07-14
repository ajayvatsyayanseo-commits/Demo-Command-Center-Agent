# Redis failure

Use for connection errors, failover, memory pressure, eviction, replication lag, or anomalous lock/
rate-limit behavior.

## Contain

1. Treat PostgreSQL uniqueness, optimistic versions, inbox/idempotency, and transactions as truth.
   Never relax booking/payment/message invariants because a Redis lease or cache is unavailable.
2. Bypass safe caches and apply conservative throttling. Pause new high-contention operations if
   the DB-backed fallback cannot stay within its capacity budget.
3. Do not infer successful deletion, idempotency, or provider state from a missing cache key.

## Recover

- Identify network/TLS/authentication, node failover, memory fragmentation/eviction, or hot-key
  pressure without exposing raw recipient/identity values.
- Restore the replication group or fail over using approved AWS procedures.
- Rewarm only versioned, non-authoritative data; never copy sensitive production payloads by hand.
- Validate compare-and-delete lease behavior, replay protection, throttling, and cache invalidation.
- Resume contention-heavy operations gradually while monitoring DB load and Redis errors.

If replay protection cannot fail closed, keep authenticated mutation endpoints paused until Redis or
an approved durable substitute is available.


# ADR-005: Payment ownership

- Status: Accepted
- Date: 2026-07-13

## Context

The website creates Cashfree subscription orders using session-bound metadata, verifies return status server-side, and has a signed webhook that only logs. It lacks durable provider order binding and exactly-once activation.

## Decision

Demo Command Center owns `demo_conversion` Cashfree orders, payment links, its canonical webhook, reconciliation, and paid transition. Existing website-originated purposes remain website-owned. A stored order binds purpose, demo, user, plan/version, approved offer, amount, currency, and expiry. Only signed/replay-checked webhook evidence and/or authenticated reconciliation can lead to paid. Website activation occurs through an idempotent gateway ledger/outbox.

## Consequences

Browser returns and user claims never activate. Duplicate webhooks are harmless. Refunds, disputes, unknown orders, amount/status mismatch, and activation disagreement enter payment review until finance contracts are approved. Cashfree routing must distinguish order purpose without two services accepting the same event.

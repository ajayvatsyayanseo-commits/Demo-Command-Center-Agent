# ADR-012: Deployment and rollback

- Status: Accepted
- Date: 2026-07-13

## Context

Stateful sagas and database changes make ad-hoc deployments and mutable image tags unsafe.

## Decision

CI builds/scans one image, records digest/SBOM, and promotes the digest through GitHub Environments. A reviewed one-off task applies backwards-compatible migrations before ECS update. Health and smoke checks gate completion. Production requires approval. Rollback selects a prior digest and disables risky features; destructive schema rollback is not automatic.

## Consequences

Application rollback is quick while migrations use expand/migrate/contract. Failed migration stops deployment. Automated pause triggers cover duplicate bookings/messages, payment mismatch, provider spikes, queue/DB pressure, model drift, PII/security incidents. Every deployment/rollback produces audit evidence.

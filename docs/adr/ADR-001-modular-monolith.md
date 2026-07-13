# ADR-001: Modular monolith

- Status: Accepted
- Date: 2026-07-13

## Context

Eight capabilities share one lifecycle, consistency boundary, identity model, and operational team. Separate services would add distributed transactions and duplicate provider ownership before scale demands it.

## Decision

Build one repository/image with clean capability modules and distinct API, worker, scheduled, evaluation, and admin process types. Modules communicate through application contracts; domain code is provider/framework independent.

## Consequences

Deployment and transactions remain coherent. Queue/process scaling is independent enough for current needs. Module import tests and ownership rules are mandatory to prevent a distributed monolith inside one process. A future extraction requires measured scaling/team evidence and a new ADR.

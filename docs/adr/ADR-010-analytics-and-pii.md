# ADR-010: Analytics and PII

- Status: Accepted
- Date: 2026-07-13

## Context

Regional monitoring/modeling needs outcomes and features, while raw messages, contacts, child data, meeting/payment details create unacceptable analytics exposure.

## Decision

Operational PostgreSQL retains scoped sensitive data per policy. An outbox produces allowlisted, pseudonymized, region/time-bucketed analytics to encrypted S3/Glue/Athena. Exports exclude phone, email, message body, meeting link, child detail, payment payload, tokens, and small cohorts. Identity tokens use a dedicated keyed transform unavailable to analysts.

## Consequences

Analytics cannot reconstruct conversations or contact users. Feature additions require privacy review and data contract versioning. Deletion propagates to operational mappings and scheduled export tombstones where legally required; immutable financial/audit records retain only lawful minimal fields.

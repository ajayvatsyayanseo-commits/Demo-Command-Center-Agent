# Rollback and pause triggers

Trigger values are environment configuration with owner/runbook, evaluation window, minimum volume, severity, and recovery criteria.

| Signal | Automated first action |
|---|---|
| Deployment health/smoke or migration failure | Stop rollout; retain/restore prior digest; do not auto-downgrade schema |
| Duplicate booking spike | Pause new bookings/scheduling; reconcile active holds/events |
| Duplicate outbound spike | Pause outbound; stop dispatcher; reconcile send keys/provider status |
| Payment mismatch/double activation attempt | Pause new payment links/activation; keep webhook inbox; finance/security ticket |
| Meta 429/5xx/quality spike | Open circuit, reduce concurrency, queue; pause noncritical outbound |
| Calendar error/duplicate conference spike | Pause new Calendar/Meet effects; reconcile operation IDs |
| Queue age/DLQ threshold | Scale within cap; pause producers/noncritical work; inspect poison messages |
| Aurora pressure/locks/storage | Shed noncritical queries, scale/failover per runbook, stop consumers safely |
| Redis failure | DB-backed conservative fallback, stricter throttles; no invariant relaxation |
| No-show anomaly/conversion collapse | Alert and disable affected strategy/model automation after sample gate |
| Model calibration/drift failure | Roll back/disable model; deterministic fallback |
| LLM schema/fallback/cost spike | Disable OpenAI task; deterministic fallback |
| PII logging incident | Pause affected paths/outbound, contain logs, privacy incident process |
| Signature/replay failure spike | Block at WAF/endpoint, rotate if compromise suspected, security incident |

Recovery requires root-cause evidence, reconciliation, fixed/canary validation, named approval, and monitored gradual re-enable. A code rollback is not proof that remote side effects were undone.

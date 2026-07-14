# Operations runbook index

These procedures preserve the architecture invariants while an incident is active. Thresholds,
owners, paging routes, and recovery objectives are environment configuration and must be approved
before production. The procedures are code-reviewed but have not been exercised against a live AWS
or provider account in this repository phase.

| Condition | Runbook |
|---|---|
| Meta outage, throttling, or quality incident | [Meta outage](meta-outage.md) |
| Google Calendar or Meet failure | [Google Calendar outage](google-calendar-outage.md) |
| Cashfree outage or webhook degradation | [Cashfree outage](cashfree-outage.md) |
| SES outage, bounce, or complaint spike | [SES outage](ses-outage.md) |
| OpenAI outage, schema failure, or cost circuit | [OpenAI outage](openai-outage.md) |
| Aurora failover or PostgreSQL unavailability | [Aurora failover](aurora-failover.md) |
| Redis failure or memory pressure | [Redis failure](redis-failure.md) |
| SQS backlog, poison message, or DLQ | [SQS backlog and DLQ](sqs-backlog-and-dlq.md) |
| Suspected duplicate booking | [Duplicate booking](duplicate-booking.md) |
| Payment mismatch or reconciliation backlog | [Payment mismatch and reconciliation](payment-mismatch-and-reconciliation.md) |
| Tutor attendance failure | [Tutor no-show](tutor-no-show.md) |
| Restricted data in logs or an unauthorized disclosure | [PII incident](pii-incident.md) |
| Scheduled or emergency credential rotation | [Secret and key rotation](secret-and-key-rotation.md) |
| Bad application release | [Deployment rollback](deployment-rollback.md) |
| Model, prompt, or extraction regression | [Model rollback](model-rollback.md) |
| Duplicate/policy-unsafe outbound delivery | [Outbound pause](outbound-pause.md) |
| Regional AWS or service-level disaster | [Disaster recovery](disaster-recovery.md) |
| Retention job, deletion request, or legal hold | [Retention and deletion](retention-and-deletion.md) |

## Alarm-to-runbook map

| Alarm family | Primary runbook |
|---|---|
| API 5xx / unhealthy ECS target | [Deployment rollback](deployment-rollback.md) |
| Signature failure spike | [Secret and key rotation](secret-and-key-rotation.md), then [PII incident](pii-incident.md) if compromise/disclosure is possible |
| Duplicate webhook spike | Provider-specific outage runbook; use [payment mismatch and reconciliation](payment-mismatch-and-reconciliation.md) for payment effects |
| Meta / Google Calendar / Cashfree provider failures | Corresponding provider outage runbook above |
| Payment reconciliation backlog | [Payment mismatch and reconciliation](payment-mismatch-and-reconciliation.md) |
| LLM fallback or model drift | [OpenAI outage](openai-outage.md) or [model rollback](model-rollback.md) |
| Conversion anomaly | [Model rollback](model-rollback.md); preserve minimum-sample regional policy and investigate non-model causes |
| No-show anomaly | [Tutor no-show](tutor-no-show.md); evaluate learner, technical, and provider cohorts before attribution |
| PII redaction failure | [PII incident](pii-incident.md) |
| Duplicate booking attempt | [Duplicate booking](duplicate-booking.md) |
| Aurora CPU/connection/availability | [Aurora failover](aurora-failover.md) |
| Redis memory/error/failover | [Redis failure](redis-failure.md) |
| Queue age/depth or non-empty DLQ | [SQS backlog and DLQ](sqs-backlog-and-dlq.md) |
| Retention/deletion failure | [Retention and deletion](retention-and-deletion.md); use [PII incident](pii-incident.md) for unauthorized retention or disclosure |

## Rules common to every incident

1. Open an incident/change reference and name an incident commander before a destructive action.
2. Preserve correlation IDs, event IDs, idempotency keys, image digest, schema/policy/model versions,
   and sanitized metrics. Never paste raw messages, contact data, meeting links, payment payloads,
   signatures, tokens, or secrets into tickets or chat.
3. Prefer the narrow kill switch. Keep durable inbox/outbox facts and provider evidence intact.
4. Do not bypass signatures, replay checks, regional scope, required confirmations, price bindings,
   or database uniqueness to restore throughput.
5. Reconcile uncertain external effects before retry or redrive. A code rollback does not undo a
   message, calendar event, or payment already accepted by a provider.
6. Record the reason, approver, commands/actions, before/after evidence, reconciliation result, and
   monitored recovery window.

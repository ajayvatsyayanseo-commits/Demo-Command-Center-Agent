# Canonical data model

All operational timestamps are `timestamptz` UTC. Original IANA timezone, source/version, tenant, region where applicable, optimistic `version`, and created/updated metadata are explicit. IDs are UUIDv7-compatible application IDs (the initial scaffold uses UUID until the generator is implemented). Sensitive values are ciphertext plus key reference; lookup uses keyed blind indexes.

| Aggregate | Tables | Core invariants |
|---|---|---|
| Demo | `demo_cases`, `demo_requirements`, `demo_participants` | One canonical case; state/version optimistic lock; requirement revisions immutable after scheduling unless rescheduled |
| Identity/privacy | `external_identity_mappings`, `consent_records`, `opt_out_records` | Unique provider/type/external ID; hashed lookup; consent purpose/version/evidence; opt-out overrides delivery |
| Conversation | `conversation_states`, `conversation_summaries` | One active flow state/version; summaries are redacted/versioned; raw history not copied into analytics |
| Tutor selection | `tutor_candidates`, `tutor_availability_snapshots` | Source snapshot/version/evidence; rankings reproducible; unknown availability is never free |
| Scheduling | `slot_proposals`, `slot_holds`, `participant_confirmations`, `demo_sessions`, `calendar_events`, `meeting_details` | UTC ranges + IANA zones; active tutor/resource ranges cannot overlap; one active session; one conference per unrelated demo |
| Reminder/comms | `reminder_policies`, `reminder_executions`, `communication_messages`, `communication_deliveries` | Policy snapshot; unique reminder occurrence; unique outbound operation; content encrypted; channel/window/consent decision audited |
| Providers | `provider_webhook_events`, `provider_request_attempts` | Unique provider/event ID; raw body encrypted with short retention; request operation/retry uniqueness |
| Outcome/quality | `demo_outcomes`, `demo_feedback`, `demo_quality_assessments` | Evidence source/time; participant feedback separated; assessment rubric/version |
| Objections/forecast | `extracted_objections`, `conversion_predictions`, `model_versions`, `feature_snapshots`, `drift_evaluations` | Evidence references required; model/prompt/features immutable/versioned; predictions never overwritten |
| Conversion | `conversion_strategies`, `approved_content_items`, `offers`, `discount_policies`, `discount_decisions` | Claims reference approved content; offer binds quote/policy/approval; no LLM authorization |
| Payment | `payment_orders`, `payment_links`, `payment_attempts`, `payment_reconciliations` | Unique provider order; purpose/demo/user/plan/amount/currency/expiry binding; one successful activation key |
| Reliability/audit | `demo_state_transitions`, `agent_inbox_events`, `agent_outbox_events`, `idempotency_records`, `audit_events` | Append-only transitions/audit; unique inbox/outbox/idempotency scopes; tamper-evident audit hash chain |
| Operations | `human_handoff_tickets`, `feature_flags`, `regional_metric_snapshots`, `alert_rules`, `alert_incidents` | One active ticket/incident per reason/rule scope; flags versioned/audited; aggregate thresholds retained |

## Scheduling constraints

PostgreSQL `btree_gist` exclusion constraints prevent overlapping active `tstzrange` holds/sessions per tutor and constrained resource. Partial unique indexes enforce one active hold per demo/proposal, one canonical calendar event per session, one Meet conference request per demo operation, and one reminder execution per policy occurrence. A hold expires by database time; workers release/mark it, but an expired row cannot protect a slot.

## Payment and delivery constraints

Partial unique indexes enforce one successful website activation per provider order and one delivered outbound operation per idempotency key. Provider webhook uniqueness is `(provider, provider_event_id)`; missing provider IDs use a canonical raw-body hash plus event timestamp scope. An idempotency key reused with a different request hash is a conflict, never a cache hit.

## Scale/partitioning

Start unpartitioned except potentially monthly `audit_events`, `provider_webhook_events`, and communication delivery history after measured volume warrants it. Preserve globally unique keys and automated future partition creation before enabling partitions. Archive encrypted immutable history to S3 only through the retention/analytics allowlist.

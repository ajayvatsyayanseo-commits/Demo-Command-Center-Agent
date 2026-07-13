# Lead Intake Agent findings

Status: code inspected at commit `c52950198d6ced38e37ab8f0f81976c04770b7a9`; live deployment and credentials are **UNVERIFIED**.

## Verified conventions

- Lead Intake declares itself the single Meta callback at `POST /v1/inbound/whatsapp`.
- Raw-body Meta HMAC verification is implemented.
- `wa_message_id` uniqueness is enforced by PostgreSQL insert-on-conflict and local-memory fallback; outbound suppression also uses a message cache.
- Signup intent is sticky-routed to Onboarding. Lead Intake sends the returned text, preserving one outbound decision.
- Structured logging and phone masking exist, although some call sites still pass raw `wa_phone` fields and therefore require a verified redaction pipeline.
- General integration routing has noop, webhook, SQS, and EventBridge clients.

## Current internal handoff

Lead Intake sends:

```json
{
  "source": "lead_intake_agent",
  "wa_message_id": "...",
  "wa_phone": "...",
  "message_text": "...",
  "timestamp": "...",
  "message_type": "...",
  "raw_payload": {}
}
```

Authentication is a static `X-NXTUTORS-INTERNAL-SECRET`. The request lacks schema version, tenant, target, actor, subject, idempotency key, causation/trace context, and PII classification. It includes more raw Meta payload than the Demo Command Center should accept.

## General event incompatibility

Existing `lead.captured`, `lead.updated`, and `handoff.requested` dataclasses use UUIDv4, no schema suffix/version, and no canonical envelope. They can target separate `tutor_matching_agent` and `scheduling_agent` names that this architecture consolidates into modules.

## Gaps

- No explicit demo-agent route or demo lifecycle handoff exists.
- No durable transactional outbox around outbound integration publication was verified.
- The 24-hour WhatsApp customer-service window and template-category selection were not found as a durable state model.
- Existing direct text sends must migrate behind the single outbound gateway/outbox contract.
- Local in-memory persistence exists when DB is absent; the Demo Command Center disallows that profile in production.

The compatibility adapter will accept only a minimized, authenticated version of the legacy payload during migration and immediately wrap it in the canonical envelope.

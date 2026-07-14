# Lead Intake contract

Target event: `whatsapp.handoff.demo.v1`, delivered to `POST /v1/internal/whatsapp/handoffs` using the canonical envelope.

Minimum payload:

```json
{
  "provider_message_ref": "opaque Meta message reference",
  "intent": "demo_request",
  "lead_ref": "opaque lead reference or null",
  "user_ref": "opaque website reference or null",
  "message": {"type": "text", "text": "minimum required user content"},
  "service_window": {"last_user_message_at": "RFC3339", "expires_at": "RFC3339"},
  "consent_refs": []
}
```

PII classification is `restricted` when message text is present. Phone stays in Lead Intake; the Demo service uses conversation/identity references. Lead Intake retries the same event/idempotency key until a durable `accepted` or `duplicate` receipt.

Demo Command Center sends the following strict body to
`POST /v1/internal/outbound/whatsapp`:

```json
{
  "event_id": "f6e89b95-c1cc-5a52-b964-0a3cdd79c71f",
  "event_type": "outbound.delivery.requested.v1",
  "demo_id": "9e383b38-5475-4815-a966-5a09c5a626d9",
  "recipient_ref": "conversation-opaque-001",
  "template_or_message_ref": "demo.collect_requirements.v1",
  "variables": {"missing_fields": "subject,preferred_times"},
  "message_category": "service",
  "service_window_expires_at": "2026-07-14T06:00:00Z",
  "send_key": "demo-requirements:f6e89b95-c1cc-5a52-b964-0a3cdd79c71f",
  "correlation_id": "corr-demo-001"
}
```

The complete body is HMAC signed with `whatsapp:send` scope. `send_key` must equal the
`Idempotency-Key` header, and `correlation_id` is repeated in `X-Correlation-Id` for trace
propagation. Lead Intake owns the final service-window, template, consent, throttling and send
decision, and publishes delivery updates. The executable request contract and example are
`contracts/lead_intake/outbound-delivery-requested.v1.schema.json` and
`contracts/lead_intake/example.outbound-delivery-requested.v1.json`.

The Demo Command Center client now serializes this target request without dropping policy or
correlation metadata. The inspected external Lead Intake deployment remains **UNVERIFIED for this
target contract** and did not expose this endpoint, so this code evidence does not establish live
compatibility. A compatibility period may accept a minimized `legacy-lead-intake.v0` adapter on a
separate authenticated route, but raw Meta payload forwarding is forbidden and the adapter has a
removal date/metric.

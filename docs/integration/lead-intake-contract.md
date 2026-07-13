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

Demo Command Center publishes `outbound.delivery.requested.v1` with recipient reference, approved template/content reference, variables classification, message category, service-window basis, and stable send key. Lead Intake owns final policy validation/send and publishes delivery updates.

Current code remains **UNVERIFIED for this target contract**. It uses a flat versionless event set and separate onboarding flat payload. A compatibility period may accept a minimized `legacy-lead-intake.v0` adapter on a separate authenticated route, but raw Meta payload forwarding is forbidden and the adapter has a removal date/metric.

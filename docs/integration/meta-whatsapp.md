# Meta WhatsApp integration

Lead Intake is the public webhook and outbound gateway (ADR-002). It verifies the raw body before JSON parsing, validates request size/content, deduplicates provider message IDs durably, acknowledges quickly after inbox insertion, and processes asynchronously.

The outbound gateway tracks last user message and 24-hour service-window expiry in UTC, conversation opt-out/STOP, approved template name/language/category/version, marketing/utility/authentication classification, recipient/tenant throttles, provider quality/429 signals, and delivery status. Free-form service replies are permitted only within the valid window and policy. Outside it, only approved templates may be selected. Each send has one stable idempotency key.

Demo Command Center never sends directly. Its provider route is disabled by default and returns no success when the durable adapter is absent. During disaster recovery, changing the public owner requires an explicit runbook action, mutual exclusion, replay position, and ADR—not simultaneous subscriptions.

Message bodies, raw payloads, phone numbers, and tokens are excluded from normal logs. Provider IDs are opaque; conversation IDs are hashed in telemetry. Webhook secret rotation supports overlapping key IDs where Meta permits it. Outbound pause, per-tenant/phone/IP/endpoint/provider limits, circuit breakers, and human incident escalation are mandatory.

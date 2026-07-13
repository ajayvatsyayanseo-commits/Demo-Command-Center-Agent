# Integration gaps and incompatibilities

| Area | Evidence | Required resolution |
|---|---|---|
| Event schema | Lead/Onboarding use unrelated flat payloads | Canonical envelope v1 plus temporary compatibility adapters |
| WhatsApp ownership | Lead owns ingress/send; Onboarding still contains provider route/sender | Keep only Lead subscribed; all agents request outbound delivery through one outbox/gateway |
| Demo identity | `demo_leads.id` is not correlated to WhatsApp conversation | Website outbox emits lead reference; identity mapping binds phone hash/provider identity after authenticated handoff |
| Tutor catalog | Two course table shapes | Website gateway returns normalized, versioned tutor DTOs |
| Availability | Website score is a placeholder | Build authoritative working-hours/exceptions source before automatic booking |
| Calendar | No verified Google Calendar ownership/config | NXTutors organizer calendar, delegated identity, unique conference request IDs |
| Payment | Website return path verifies server-side but order binding is session-only; webhook only logs | Demo service owns conversion order and durable Cashfree webhook/reconciliation; website activation is idempotent gateway command |
| Subscription activation | `updateOrCreate` by user/type has no provider activation key | Add gateway idempotency/activation ledger and transactional outbox |
| Email | Website defaults to log mailer; SES config exists but live delivery is unverified | Demo service SES port with verified identity/configuration health |
| Authorization | No region membership found | Gateway-issued admin claims plus repository region filtering and audited override |
| Scheduling | No hold/confirmation/calendar records | PostgreSQL-owned saga and exclusion/unique constraints |
| Service window | Durable Meta 24-hour window not found | Store last user message/window expiry and enforce category/template policy centrally |
| Outbox | No end-to-end transactional outbox verified | Durable inbox/outbox in Demo service and Laravel adapter |
| Runtime | Lead uses documented Python 3.11; target is 3.12 | Contracts remain language-neutral; deploy this service on Python 3.12 |

No direct cross-database write or distributed transaction is permitted. Temporary read-only access would require a new accepted ADR; none is accepted in this phase.

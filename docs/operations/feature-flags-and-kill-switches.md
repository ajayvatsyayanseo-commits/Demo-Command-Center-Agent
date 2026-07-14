# Feature flags and kill switches

Startup flags are typed environment settings with safe defaults. A tenant-scoped runtime-flag table is
modeled, but a versioned/audited runtime flag loader is not yet wired; do not claim tenant-specific
dynamic control from that table. The safe-off behavior below is the target policy. Only rows marked
`Enforced` have a code-present runtime boundary in the current implementation.

| Flag | Safe-off behavior | Current code status |
|---|---|---|
| `DEMO_COMMAND_CENTER_ENABLED` | Keep every registered inbox event unclaimed; retain durable ingress and health/operations | Enforced in inbox selection |
| `DEMO_SCHEDULING_ENABLED` | No new holds/calendar effects; human scheduling | Configuration validation only |
| `DEMO_REMINDERS_ENABLED` | Cancel/suppress new reminders; preserve bookings | Not yet wired to a dispatcher |
| `DEMO_FORECASTING_ENABLED` | No score; deterministic strategy/human review | Not yet wired to runtime evaluation |
| `DEMO_OBJECTION_EXTRACTION_ENABLED` | No inferred objections; explicit evidence/manual review | Not yet wired to runtime extraction |
| `DEMO_POST_CONVERSION_ENABLED` | Do not queue new onboarding; keep accepted onboarding inbox/outbox rows unclaimed | Enforced in recorder, inbox, and outbox selection |
| `DEMO_DISCOUNTS_ENABLED` | Full approved price only/human flow | Not yet wired to runtime offer commands |
| `DEMO_PAYMENTS_ENABLED` | Keep Cashfree inbox/outbox work unclaimed and reject new provider/order effects | Enforced at provider, inbox, and outbox/order boundaries |
| `DEMO_OUTBOUND_PAUSED` | Keep Lead-targeted rows queued without consuming attempts; process inbound/state safely | Enforced in outbox selection |
| `DEMO_NEW_BOOKINGS_PAUSED` | Keep new WhatsApp demo-handoff rows unclaimed; existing lifecycle work remains durable | Enforced in inbox selection |
| `DEMO_GOOGLE_MEET_ENABLED` | No Meet creation; use approved manual/alternate flow | Configuration validation only |
| `DEMO_OPENAI_ENABLED` | Deterministic fallback | Configuration validation only |
| `DEMO_AUTOMATIC_DISCOUNT_ENABLED` | Must remain false; LLM/automation cannot authorize concessions | Enforced by settings rejection |
| `DEMO_AUTOMATIC_PAYMENT_LINK_ENABLED` | Must remain false until a reviewed payment-link flow exists | Enforced by settings rejection |
| `CASHFREE_PAYMENT_LINK_ENABLED` | Must remain false because only the bound hosted-order/session flow is implemented | Enforced by settings rejection |

Payment/outbound incident flags distinguish new effects from reconciliation of already-accepted
external facts. Changes to startup settings require the controlled deployment/restart path. Runtime
tenant overrides and cache-failure behavior remain design intent until the runtime flag loader is
implemented and tested.

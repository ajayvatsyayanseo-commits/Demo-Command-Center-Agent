# Feature flags and kill switches

Flags are environment/tenant scoped, versioned, cached briefly, and audited with actor/reason/expiry. Safe production defaults disable new external effects until validated.

| Flag | Safe-off behavior |
|---|---|
| `DEMO_COMMAND_CENTER_ENABLED` | Reject new handoffs; retain health/operations |
| `DEMO_SCHEDULING_ENABLED` | No new holds/calendar effects; human scheduling |
| `DEMO_REMINDERS_ENABLED` | Cancel/suppress new reminders; preserve bookings |
| `DEMO_FORECASTING_ENABLED` | No score; deterministic strategy/human review |
| `DEMO_OBJECTION_EXTRACTION_ENABLED` | No inferred objections; explicit evidence/manual review |
| `DEMO_POST_CONVERSION_ENABLED` | No automated draft/delivery |
| `DEMO_DISCOUNTS_ENABLED` | Full approved price only/human flow |
| `DEMO_PAYMENTS_ENABLED` | No new payment orders; still reconcile already accepted events under incident policy |
| `DEMO_OUTBOUND_PAUSED` | Queue/suppress sends; process inbound/state safely |
| `DEMO_NEW_BOOKINGS_PAUSED` | No new holds; existing sessions/reminders continue as policy allows |
| `DEMO_GOOGLE_MEET_ENABLED` | No Meet creation; use approved manual/alternate flow |
| `DEMO_OPENAI_ENABLED` | Deterministic fallback |
| `DEMO_AUTOMATIC_DISCOUNT_ENABLED` | Must remain false; LLM/automation cannot authorize concessions |
| `DEMO_AUTOMATIC_PAYMENT_LINK_ENABLED` | Human/explicit user-confirmed creation only |

Payment/outbound incident flags distinguish new effects from reconciliation of already-accepted external facts. Cache failure reads the safer value or pauses the capability; it never defaults automation on.

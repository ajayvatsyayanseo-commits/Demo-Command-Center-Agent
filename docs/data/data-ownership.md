# Data ownership

| Data | System of record | Demo service access |
|---|---|---|
| Website users/admins, legacy `register` profiles | Laravel/MySQL | Versioned gateway read/command only |
| Tutors, course/subject mappings, reviews | Laravel/MySQL | Normalized gateway snapshot; no direct writes |
| Plans, prices, subscriptions, legacy orders | Laravel/MySQL | Authoritative quote and idempotent activation commands |
| Demo lifecycle/scheduling/reminders/outcomes | Demo PostgreSQL | Read/write by owned repositories |
| Cashfree demo-conversion orchestration | Demo PostgreSQL + Cashfree evidence | Owned adapter and reconciliation |
| WhatsApp inbound/outbound delivery | Lead Intake/outbound gateway | Canonical handoff and delivery events |
| Signup/onboarding lifecycle | Onboarding Agent | Paid handoff/acknowledgement events |
| Calendar/Meet provider state | Google; mirrored operation state in Demo DB | Port with reconciliation |
| Analytics artifacts | Sanitized S3/Glue/Athena | Allowlisted export only |

No Python code writes arbitrary Laravel tables. The gateway validates authenticated service scope, tenant/region, request schema, optimistic source version, and idempotency key. Laravel mutations and its outbox commit together. Cross-system operations are sagas; there is no cross-database transaction assumption.

The Demo service does not use MySQL `DB_*` credentials at runtime. The repository may contain
adapter-scoped placeholder names for the Laravel website deployment (`DB_*` inside the adapter
package or `NXTUTORS_WEBSITE_DB_*` in example configuration), but production values stay in the
Laravel/AWS secret boundary. The Laravel adapter reads `register` inside the website deployment and
exposes only safe projections: profile/tutor summaries, plan quotes, activation commands, and
purpose-bound contact references. Scheduling uses `register.phone` through `phone-resolve`
endpoints that return opaque WhatsApp recipient references, not raw phone numbers.

# Failure modes

| Failure | Detection | Safe behavior / compensation |
|---|---|---|
| Duplicate inbound event | Inbox uniqueness | Return duplicate acknowledgement; no replayed side effect |
| PostgreSQL unavailable | readiness, pool/latency alarms | Stop consuming; SQS retains work; API 503 |
| Redis unavailable | cache/lock metrics | Bypass cache; use DB constraints/locks; throttle conservatively |
| Website gateway unavailable | circuit breaker | Queue retry; do not invent tutors/quotes or activate payment |
| Slot conflict | exclusion/unique constraint | Reject hold and propose another slot |
| Calendar create timeout | operation record + reconciliation | Look up deterministic external ID before retry; release hold only after outcome known |
| Calendar succeeds, notification fails | delivery status | Keep booking; retry delivery; ticket after budget |
| Meta outage/429 | gateway telemetry | Queue, respect Retry-After, open circuit; never direct-send from this service |
| Cashfree duplicate/replay | signature/time window/event unique key | Acknowledge stored duplicate; activate at most once |
| Cashfree amount mismatch | bound order comparison | `PAYMENT_REVIEW`; no paid transition |
| Website activation fails after paid | payment saga state | Persist verified payment; retry idempotent activation; urgent ticket |
| Onboarding unavailable after paid | outbox age/retries | Remain `PAID`; retry safely; human ticket; accurate user message |
| OpenAI unavailable/schema invalid | circuit/schema metrics | Deterministic summary/template fallback or human review; no state/payment impact |
| Forecast drift/calibration failure | scheduled evaluation | Disable forecast-driven recommendations; retain service access |
| Poison queue item | retry counter | DLQ with redacted metadata; explicit inspected redrive |
| PII log incident | scanners/audit | outbound pause, contain, rotate if needed, delete/notify per incident plan |

Retries are bounded, jittered, provider-specific, and limited to safe/idempotent operations. The user-facing response carries a correlation ID but not internal diagnostics.

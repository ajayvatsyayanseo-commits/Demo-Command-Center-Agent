# Observability

Propagate W3C trace context and correlation/causation across HTTP, SQS, outbox, scheduler, provider attempt, and agent event. Logs use the privacy allowlist. Metrics have bounded-cardinality dimensions (environment, tenant class, coarse region, event/operation/provider/result/version) and never user/demo IDs where unbounded.

Dashboards cover ingress/handoff, funnel/state duration, scheduling/holds/calendar, reminders/messages/window/template, no-shows/quality, forecasting/calibration/drift, objections/conversion/offers, payments/activation/reconciliation, onboarding, queues/DLQs, provider latency/error/429/circuits, DB pool/locks/storage, Redis fallback, security/replay/rate limits, human handoff, OpenAI tokens/cost/schema/fallback, and unit economics.

Required metrics include all items in the project brief: webhook count/duplicates; handoff failures; delivery/response/match/schedule times; hold conflicts; confirmation/reschedule/no-show/completion; quality/objection distributions; prediction calibration; conversion/regional metrics; payment/replay; queue age/depth; provider/DB/Redis; handoff; LLM; and cost per scheduled/completed/paid demo.

Alarms link to a runbook, owner, severity, environment, current version, and correlation-safe query. High-cardinality debugging uses sampled traces and indexed operational references, not metric labels or raw content.

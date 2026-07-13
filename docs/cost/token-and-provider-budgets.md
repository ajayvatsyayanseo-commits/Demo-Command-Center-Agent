# Token and provider budgets

Deterministic code handles state, scheduling, payment, rules, eligibility, templates, routing, and numeric forecasting. OpenAI is invoked only for eligible bounded language tasks after redaction.

Each task policy defines model reference, prompt/schema version, maximum input/output tokens, maximum history summary size, tool depth (normally zero), retries, timeout, per-user/tenant daily usage, global daily/monthly money budget, and deterministic fallback. Reservation occurs before the call and settles from actual usage. Budget exhaustion disables the optional task without blocking scheduling/payment truth.

Cache only safe non-personal deterministic outputs by content/policy/model version. Summaries replace full histories; no cross-user response cache. Provider HTTP calls have concurrency limits, circuit breakers, Retry-After handling, and measured unit-cost attribution. Expensive evaluation/training uses separate queues/tasks and can be stopped independently.

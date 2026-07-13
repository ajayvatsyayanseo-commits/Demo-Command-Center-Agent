# Abuse and rate limiting

Rate policy is configuration/database-owned and versioned. Dimensions include source IP, provider identity/phone hash, canonical user, tenant, region/admin, endpoint, event type, and downstream provider. Limits combine short burst token buckets, sustained windows, concurrency, payload size, and daily cost budgets.

Public provider callbacks are allowed enough burst for provider retries but still require signatures; invalid signature/replay spikes block earlier at WAF. Internal limits reject abusive callers without acknowledging unpersisted events. User messaging respects STOP/opt-out immediately and maintains quiet hours/template/service-window rules.

Abuse score signals: invalid signatures, replay/duplicate ratio, malformed payloads, rapid conversation resets, slot-hold churn, payment/order churn, repeated discount attempts, identity conflicts, suspicious admin exports, provider 429s, and prompt-injection indicators. Actions progress through delay, challenge/verification, temporary scope block, outbound pause, and human/security ticket. Never deny safeguarding/human contact solely on a model score.

All blocks have reason, scope, expiry, policy version, correlation, and audited override. Redis may implement counters; durable security incidents and high-value decisions persist in PostgreSQL.

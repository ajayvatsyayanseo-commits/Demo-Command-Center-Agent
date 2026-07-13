# Incident response

Severity and ownership are defined in the on-call system. Immediate priorities are human safety, stopping duplicate/financial effects, preserving evidence, containing credential/PII exposure, and accurate communication.

1. Detect/triage from alarm, security report, provider notice, or audit anomaly; create incident ID and commander.
2. Contain using granular flags: pause outbound/new bookings/payments/discounts/OpenAI/provider route, stop consumers, block key/IP, or revoke secret.
3. Preserve sanitized logs/traces/audit/outbox/inbox evidence and image/config versions without copying raw PII to chat/tickets.
4. Eradicate/recover: rotate keys, patch, reconcile bookings/payments/deliveries, redrive inspected events, validate health and invariants.
5. Notify legal/privacy/provider/users according to approved obligations; never speculate.
6. Review root cause, blast radius, timeline, missed controls, cost, and corrective owners/dates.

Payment mismatch/double activation, duplicate booking/message spike, signature failure spike, PII logging, safeguarding complaint, unauthorized regional export, and compromised credential are page-worthy. Rollback alone is insufficient when external side effects occurred; run reconciliation and compensation.

# SES outage

Use for send failures, throttling, account suspension, bounce/complaint spikes, or missing delivery
events.

## Contain

1. Open the SES circuit or disable affected email templates. Do not invalidate a confirmed booking
   solely because email failed.
2. Preserve delivery requests with the same idempotency key; do not send through an unapproved
   personal mailbox or expose tutor addresses to learners.
3. Suppress addresses with authoritative bounce/complaint evidence and stop marketing messages
   when consent or reputation is uncertain.

## Diagnose and recover

- Check verified identity, production access, quotas, configuration/event routing, template
  existence, throttling, and suppression status.
- Separate provider acceptance from delivery; compare stored provider message references and
  delivery state without logging recipient data.
- Canary an approved template to controlled test recipients, then verify acceptance and event
  processing.
- Drain transactional confirmations first within the communication policy; escalate expired
  confirmation SLAs to human handoff. Resume noncritical messages gradually.

Escalate account/reputation issues to AWS/communications owners and consent or disclosure issues to
privacy/legal.


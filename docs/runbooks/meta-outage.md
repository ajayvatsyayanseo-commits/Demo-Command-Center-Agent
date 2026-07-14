# Meta outage

Use for Meta 429/5xx, delivery-status gaps, number quality degradation, or a Lead Intake outage.
Lead Intake remains the only public Meta webhook and outbound WhatsApp sender; Demo Command Center
must never become a simultaneous fallback sender.

## Contain

1. Set the approved outbound pause at the canonical sender and set
   `DEMO_OUTBOUND_PAUSED=true` for Demo Command Center through the controlled configuration path.
2. Leave inbound/outbox records durable. Do not delete, re-key, or repeatedly republish them.
3. If the incident is policy/quality related, stop non-transactional messages first. Preserve only
   explicitly approved safety/transactional handling.
4. Keep `META_DIRECT_WEBHOOK_ENABLED=false` and `META_OUTBOUND_ENABLED=false` here.

## Diagnose

- Separate Lead Intake unavailability from Meta API failure, throttling, template rejection,
  service-window rejection, and number-quality enforcement.
- Inspect bounded provider status/error metrics, outbox oldest age, retry count, and circuit state.
- Confirm the same idempotency key is retained across retries and no second sender is subscribed.
- Check Meta status/account consoles only through approved operator access; do not copy tokens or
  recipient data into incident records.

## Recover

1. Resolve account/template/quality issues with the product and communications owner.
2. Canary one approved template or an in-window service message through Lead Intake.
3. Verify one provider acknowledgement and delivery update maps to one durable send operation.
4. Drain in priority order with provider `Retry-After`, quiet hours, opt-out, service-window, and
   global/recipient throttles enforced. Re-enable noncritical traffic gradually.

Escalate to Meta/account operations and privacy/legal when policy, consent, child data, or user
notification obligations are involved. Record queue recovery time and duplicate-send checks.


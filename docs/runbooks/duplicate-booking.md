# Duplicate booking

Use when overlapping active holds/sessions or multiple Calendar events may exist for the same tutor,
resource, and time range.

## Contain

1. Pause new bookings for the affected tenant/region or globally, based on verified scope. Do not
   cancel either booking until facts and participant impact are known.
2. Preserve hold/session rows, state transitions, idempotency keys, provider operation records, and
   Calendar IDs/etags. Do not edit them directly.
3. Open an urgent human-handoff ticket for operations to coordinate truthful participant messaging.

## Reconcile

- Establish authoritative UTC ranges plus original IANA timezones, tutor/resource, hold expiry,
  required confirmations, and case/session versions.
- Query the NXTutors organizer calendar by private demo reference and compare provider events.
- Distinguish duplicate proposal, expired hold, overlapping active hold, duplicate provider event,
  and true participant double booking.
- Select compensation under approved operations policy: retain the valid earliest/confirmed
  booking, obtain consent for a replacement, update/cancel Calendar idempotently, and reschedule
  reminders. Never silently substitute a tutor or time.

## Recover

Re-run the collision/concurrency tests, verify the PostgreSQL exclusion/unique constraint and
migration are present, canary concurrent holds, and monitor conflicts before reopening. Document
every affected demo and the participant remedy.


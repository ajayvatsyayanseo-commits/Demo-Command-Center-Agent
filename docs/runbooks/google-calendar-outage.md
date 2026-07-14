# Google Calendar and Meet outage

Use for free/busy failures, event create/update/delete uncertainty, duplicate events, missing Meet
links, or delegated-identity failures.

## Contain

1. Pause new Google effects and, when safe scheduling cannot be proven, pause new bookings. Keep
   existing confirmed sessions and notification facts intact.
2. Never report a demo as scheduled merely because a provider request was sent.
3. Do not release a valid old booking during reschedule until the replacement outcome is known.
4. Keep meeting URIs encrypted and out of logs/tickets.

## Reconcile

- Classify each operation as not attempted, confirmed success, confirmed failure, or uncertain.
- For uncertain creates, query the NXTutors-controlled calendar by private `demo_id` and stable
  operation/conference request reference before retrying.
- Compare the stored provider event ID/etag and session version. Do not overwrite a newer event.
- For pending conference data, poll through bounded durable work; do not create another unrelated
  conference to obtain a link.
- If Calendar succeeded but notification failed, keep the booking and retry only notification.

## Recover

Canary free/busy, one event create with a unique Meet request ID, reconciliation lookup, and safe
cancellation using non-production test identities. Resume bookings gradually after duplicate-event,
hold-conflict, and notification metrics remain normal. Escalate credential/delegation issues to the
Workspace administrator and privacy issues to the privacy owner.


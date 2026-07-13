# Scheduling and rescheduling saga

## Initial scheduling

```mermaid
sequenceDiagram
    participant A as Application
    participant W as Website gateway
    participant DB as PostgreSQL
    participant G as Google Calendar
    participant Q as Outbound gateway
    A->>W: normalized tutor/availability snapshot
    A->>G: free/busy for configured calendars
    A->>DB: propose slots in participant timezones
    A->>DB: atomically create expiring hold
    A->>Q: request participant confirmations
    Q-->>A: confirmation events
    A->>DB: lock case + verify all/hold active
    A->>G: create event + unique conferenceRequestId
    G-->>A: event id / conference pending or ready
    A->>DB: persist calendar/meeting + SCHEDULED + outbox
    A->>Q: confirmation delivery requests
```

Use UTC `timestamptz` plus original IANA zones. Working hours, exceptions, buffers, mode/location feasibility, website availability, and Calendar free/busy are separate evidence with capture timestamps. Unknown availability cannot be treated as free.

An active hold is protected by a PostgreSQL range exclusion constraint per tutor/resource (planned in scheduling migration) and a unique active operation key. Redis may reduce contention but cannot establish the booking. Hold TTL/confirmation deadlines are policy values. Calendar creation uses a stable operation record, external extended property `demo_id`, and deterministic unique conference request ID; retries first reconcile before creating.

## Rescheduling

```mermaid
sequenceDiagram
    participant U as User/Tutor
    participant A as Application
    participant DB as PostgreSQL
    participant G as Calendar
    participant S as Scheduler
    U->>A: reschedule request
    A->>DB: SCHEDULED -> RESCHEDULE_REQUESTED
    A->>S: cancel pending reminders
    A->>DB: negotiate and hold replacement slot
    A->>G: update existing event or create replacement operation
    alt calendar update succeeds
      A->>DB: release old hold, commit new session/version
      A->>S: schedule new reminders
    else update fails
      A->>DB: keep prior booking or mark compensation pending
      A->>A: bounded retry / human ticket
    end
```

Never release a still-valid old booking before the replacement is durably secured unless policy explicitly accepts the gap. Notification failure does not cancel a valid calendar event; it queues retry and escalates after budget exhaustion. Calendar creation failure releases the provisional hold and returns to negotiation.

# Demo state machine

`src/demo_command_center/state/transitions/table.py` is the executable registry. Each transition declares command, allowed actors, guards, side effects, and compensation. Each accepted transition is stored with before/after state, reason, UTC time, correlation, idempotency key, flow/policy/model version, requested/completed effects, failure, and compensation.

```mermaid
stateDiagram-v2
    [*] --> NEW
    NEW --> QUALIFYING
    QUALIFYING --> TUTOR_MATCHING
    TUTOR_MATCHING --> TUTOR_SHORTLISTED
    TUTOR_SHORTLISTED --> SLOT_NEGOTIATING
    SLOT_NEGOTIATING --> SLOT_HELD
    SLOT_HELD --> AWAITING_CONFIRMATIONS
    SLOT_HELD --> SLOT_EXPIRED
    AWAITING_CONFIRMATIONS --> SCHEDULED
    SCHEDULED --> REMINDERS_ACTIVE
    REMINDERS_ACTIVE --> READY
    READY --> IN_PROGRESS
    READY --> NO_SHOW_USER
    READY --> NO_SHOW_TUTOR
    IN_PROGRESS --> COMPLETED
    IN_PROGRESS --> TECHNICAL_FAILURE
    COMPLETED --> ANALYSIS_PENDING
    ANALYSIS_PENDING --> ANALYZED
    ANALYZED --> CONVERSION_FOLLOW_UP
    CONVERSION_FOLLOW_UP --> OFFER_PENDING
    CONVERSION_FOLLOW_UP --> PAYMENT_PENDING
    OFFER_PENDING --> PAYMENT_PENDING
    PAYMENT_PENDING --> PAID
    PAYMENT_PENDING --> PAYMENT_FAILED
    PAYMENT_PENDING --> PAYMENT_EXPIRED
    PAYMENT_PENDING --> PAYMENT_REVIEW
    PAID --> ONBOARDING_HANDOFF
    ONBOARDING_HANDOFF --> CONVERTED
    SCHEDULED --> RESCHEDULE_REQUESTED
    REMINDERS_ACTIVE --> RESCHEDULE_REQUESTED
    RESCHEDULE_REQUESTED --> SLOT_NEGOTIATING
```

Cancellation, human handoff, and terminal failure transitions are registered from eligible states. Orthogonal confirmation, hold, attendee, delivery, calendar, and payment status stay in dedicated records rather than multiplying lifecycle states. Optimistic `version` checks and transition idempotency prevent conflicting updates.

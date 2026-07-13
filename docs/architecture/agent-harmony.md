# Agent harmony

Lead Intake owns the shared public Meta webhook and the single outbound WhatsApp send decision. Demo Command Center owns demo lifecycle after a `demo.requested.v1`/`whatsapp.handoff.demo.v1` acknowledgement. Onboarding owns signup after an accepted paid handoff.

```mermaid
sequenceDiagram
    participant M as Meta
    participant L as Lead Intake
    participant D as Demo Command Center
    participant O as Onboarding
    M->>L: signed inbound message
    L->>L: verify + deduplicate + route intent
    L->>D: signed whatsapp.handoff.demo.v1
    D-->>L: durable acceptance / duplicate
    D->>D: progress demo lifecycle
    D->>L: outbound.delivery.requested.v1
    L->>M: exactly-once send
    M-->>L: delivery status
    L->>D: outbound.delivery.updated.v1
    D->>O: onboarding.paid-user.requested.v1
    O-->>D: onboarding.handoff.accepted.v1
    O-->>D: onboarding.completed.v1
    D->>L: welcome delivery request
```

Every event uses the canonical envelope, an operation-stable idempotency key, correlation/causation IDs, and minimized payload. A receiver acknowledges only after durable inbox insertion. Synchronous reply text in legacy handoffs is a migration adapter, not the durable target contract.

If Lead Intake is unavailable, outbound requests stay queued; Demo Command Center never calls Meta as a fallback. If Onboarding is unavailable, `PAID` remains durable, an outbox retry is scheduled, and a ticket opens when the retry budget expires.

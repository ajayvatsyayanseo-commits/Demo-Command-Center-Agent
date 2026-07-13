# Payment and paid-transition saga

```mermaid
sequenceDiagram
    participant U as User
    participant D as Demo Command Center
    participant W as Website gateway
    participant C as Cashfree
    participant O as Onboarding
    D->>W: fetch authoritative plan quote
    W-->>D: plan/version/amount/currency/user binding
    D->>D: persist order intent + idempotency
    D->>C: create order/payment link
    C-->>D: provider order reference
    D-->>U: checkout request via outbound gateway
    C->>D: signed webhook
    D->>D: durable inbox + replay/duplicate check
    D->>C: server-side reconcile when needed
    D->>D: verify purpose, amount, currency, user, plan, offer, demo, expiry
    D->>W: idempotent activate-subscription command
    W-->>D: activation reference
    D->>D: transition PAYMENT_PENDING -> PAID once
    D->>O: onboarding.paid-user.requested.v1
    O-->>D: accepted / completed event
    D-->>U: welcome delivery request
```

The Demo Command Center owns orders created for demo conversion. The website continues to own unrelated subscription checkout flows. `order_purpose=demo_conversion` selects the owner and callback path.

Browser returns and WhatsApp claims are never payment evidence. The canonical transition requires valid raw-body signature, timestamp/replay checks, durable provider event uniqueness, bound order fields, and either a verified successful event or authenticated provider reconciliation. A unique activation key spans provider order and website subscription activation.

Amount/status mismatch, unknown order, duplicate account ambiguity, refund, dispute, or activation disagreement enters `PAYMENT_REVIEW` and opens a redacted human ticket. Refund/dispute processing is not automated until finance policy and website reversal contracts are approved.

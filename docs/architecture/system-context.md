# System context

```mermaid
flowchart LR
    User["Learner / guardian"] -->|WhatsApp| Meta[Meta WhatsApp]
    Meta --> Lead[Lead Intake Agent<br/>canonical ingress + sender]
    Lead -->|signed canonical events| DCC[Demo Command Center Agent]
    DCC -->|delivery requests| Lead
    DCC -->|versioned API| Web[Laravel Integration Gateway]
    Web --> MySQL[(Legacy MySQL<br/>profiles, tutors, plans, subscriptions)]
    DCC --> PG[(Aurora PostgreSQL<br/>demo lifecycle)]
    DCC --> Redis[(Redis<br/>cache/locks only)]
    DCC --> Calendar[Google Calendar / Meet]
    DCC --> Cashfree[Cashfree]
    DCC --> SES[Amazon SES]
    DCC --> OpenAI[OpenAI<br/>bounded language tasks]
    DCC -->|paid handoff| Onboarding[Onboarding Agent]
    Admin[Regional operations] -->|Laravel auth + scoped token| DCC
```

Trust boundaries exist at every arrow. Provider callbacks enter only signature-specific endpoints; internal calls use audience-bound authentication and replay protection. PostgreSQL is authoritative for lifecycle state; Redis never decides durable truth.

# PII data map and boundaries

```mermaid
flowchart LR
    User -->|raw WhatsApp content/phone| Lead[Lead Intake restricted store]
    Lead -->|opaque refs + minimized restricted payload| Demo[Demo operational boundary]
    Demo -->|purpose-bound tutor/user refs| Web[Website gateway]
    Web -->|authoritative minimized profile fields| Demo
    Demo -->|attendee email / encrypted meeting data| Google[Google Calendar]
    Demo -->|customer/order minimum| Cashfree
    Demo -->|consented recipient| SES
    Demo -->|redacted bounded text| OpenAI
    Demo -->|allowlisted pseudonymous facts| Analytics[S3 / Athena analytics boundary]
```

Restricted: phone/email/name/address, free-form messages/feedback/evidence, guardian-child relationship/details, tutor private contact/documents, meeting links, calendar attendees, payment/customer payload, IP/user-agent, consent evidence, and provider tokens. Low/metadata: opaque IDs, coarse locale/region, delivery/provider status. Non-PII requires a documented allowlist.

Data is collected by purpose, encrypted in transit/at rest, field/envelope encrypted when highly sensitive, role/tenant/region scoped, retention tagged, and excluded from normal logs. Analytics gets only pseudonymous/coarse facts. External processors receive the minimum for the active operation and no unrelated conversation history.

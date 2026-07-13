# Canonical agent event envelope

Version 1.0 is defined by `contracts/events/agent-event-envelope.v1.schema.json` and `AgentEventEnvelope`. Event types include a major suffix such as `demo.slot.confirmed.v1`; semantic payload schemas are independently versioned and referenced by event type.

Required metadata: sortable unique event ID, event type/schema version, UTC occurrence, source/target agent, tenant/nullable region, correlation/causation/conversation, typed actor, opaque subject references, stable idempotency key, optional W3C trace context, PII classification, and typed payload.

Envelope metadata must never contain raw phone, email, message, meeting link, child detail, payment detail, or token. Restricted payload fields are minimized, encrypted at rest, redacted from telemetry, and omitted from analytics.

Receivers authenticate the raw request, check timestamp/audience/key ID/replay nonce, validate content type/size/schema, insert the complete event into a unique inbox, and only then return acceptance. Unknown additive payload fields are rejected within v1 unless the payload schema explicitly permits them. Unsupported versions return a stable `DCC_INVALID_EVENT` error and create no effects.

Idempotency key semantics are operation-specific and stable across retries (for example `demo:{demo_id}:calendar:create:{session_version}`). Reusing a key with different canonical request hash is an error. `event_id` identifies a delivery fact; `idempotency_key` identifies the business operation.

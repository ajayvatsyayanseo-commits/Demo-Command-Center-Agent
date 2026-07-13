# WhatsApp Onboarding Agent findings

Status: code inspected at commit `8e867531f768a916cb9df33c7a10f2b10e3aa4c1`; deployment and provider behavior are **UNVERIFIED**.

## Reusable conventions

- Deterministic state machine and command handling.
- Separate student/tutor flows and validators.
- Cache key/TTL policy, row-locked state repository, webhook event store, queue jobs, health endpoints, PII masking, terms/consent records, retention workflows, and human handoff tickets.
- Legacy `register` mapping isolates misspelled fields and stores password hashes rather than plaintext confirmation passwords.
- Internal handoff rejects absent/mismatched secrets and uses `Cache::add` for one-day message ID deduplication.

## Handoff behavior

`POST /whatsapp/onboarding/webhook` distinguishes the internal payload from a genuine Meta payload. On the internal path it validates the shared secret, detects role, suppresses duplicate message IDs, and returns `reply_text`; it does not send WhatsApp.

The inspected internal controller path does not persist the forwarded event or run the full queued conversation orchestrator before replying. Its idempotency record is cache-only. This is inadequate for paid-to-onboarding exactly-once handoff and must be upgraded behind a durable canonical inbox.

## Ownership conflicts

The package retains a genuine Meta webhook path and binds `MetaMessageSender`. Those are compatibility capabilities, not the target topology. Only Lead Intake may be registered for the shared public number; Onboarding must receive canonical internal events and return commands/drafts through the outbound gateway.

The package writes the website `register` table through a local adapter. For the new service, website mutations are instead mediated through the authenticated website gateway. Onboarding may continue its existing compatibility path until separately migrated.

## Contract incompatibilities

- Static shared-secret header without timestamp/key ID/replay signature.
- Raw phone, message text, and raw provider payload.
- No schema version, tenant, subject mapping, PII classification, causation, or trace context.
- Reply response shape (`status`, `reply_text`) is synchronous and not a canonical acknowledgement event.
- Cache-only duplicate window can expire independently of durable lifecycle records.

The Demo Command Center emits `onboarding.paid-user.requested.v1`; Onboarding must answer with `onboarding.handoff.accepted.v1`, `completed.v1`, or `failed.v1` using the shared envelope.

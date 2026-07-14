# Retention, deletion, and legal hold

Use for scheduled retention cleanup, an authenticated data-subject request, failed downstream
deletion, or a new/removed legal hold. Retention periods, lawful basis, approvers, and notification
rules require privacy/legal and business approval; no duration is inferred by the application.

## Prepare

1. Verify the requester's identity/authority and resolve opaque identities across Demo Command
   Center, Laravel, Lead Intake and Onboarding without exposing search results across tenants/regions.
2. Load the approved policy reference and classify operational, message/meeting, provider, payment,
   audit/security, analytics/model and backup records.
3. Check legal hold, dispute, safeguarding, fraud and financial-record obligations. A legal hold
   blocks eligible deletion and requires an audited reason/owner/expiry review.
4. Produce a dry-run count and downstream plan; never print record content, contact data, meeting
   links, payment payloads or secret material.

## Execute and propagate

- Use the guarded retention command only with the approved policy reference and bounded batch size.
- Delete or anonymize purpose-expired restricted payloads first; preserve only lawful minimal
  financial/audit facts and their opaque reconciliation references.
- Expire meeting URIs and message/provider bodies independently of lifecycle metadata.
- Propagate a tracked saga to the website gateway, Lead Intake, Onboarding, S3 analytics/model
  exports and cache invalidation. Emit tombstones where approved; Redis deletion alone is not proof.
- Backups age out through the approved lifecycle and must not reintroduce deleted data into live use.

## Verify and close

Re-run the scoped lookup, confirm each downstream acknowledgement or assigned exception, verify
analytics suppression/tombstones and cache invalidation, and record counts/policy version without
PII. Retry only idempotently. Escalate missed deadlines, ambiguous identity, legal-hold conflict, or
unauthorized retention/deletion as a privacy incident.

# PII or restricted-data incident

Use for restricted data in logs/analytics/tickets, unauthorized regional access/export, leaked
meeting/payment/contact data, credential exposure, or incorrect processor disclosure.

## Contain immediately

1. Open a security/privacy incident and name an incident commander. Pause the affected path and, if
   further disclosure is possible, outbound delivery/export/model processing.
2. Restrict access to affected logs/buckets/queues; preserve access and audit evidence without
   duplicating the sensitive content.
3. Revoke/rotate exposed credentials and links. Do not destroy evidence or broadly purge before the
   privacy/security owner establishes scope and legal-hold requirements.
4. Use hashes/opaque references in incident communication. Never paste the exposed value into a
   ticket to demonstrate it.

## Assess and recover

- Establish data classes, subjects/guardian-child context, tenant/region, recipients/processors,
  access/download evidence, start/end time, backups/exports, and ongoing exposure.
- Fix the source, validate redaction/authorization/analytics allowlists, and propagate an approved
  deletion/tombstone through Demo DB, website gateway, Lead Intake, Onboarding, caches, and S3.
- Restore only after canary log scans and access tests show no restricted content or cross-region
  leak.
- Monitor for recurrence and record corrective owners/dates.

Privacy/legal must determine notification, preservation, deletion, child-data, contractual, and
regulatory obligations. This runbook and the code do not guarantee compliance.


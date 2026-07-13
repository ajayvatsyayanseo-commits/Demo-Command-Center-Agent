# Security policy

Report suspected vulnerabilities privately to the NXTutors security owner; do not open a public issue containing exploit details or personal data.

Never commit credentials, webhook payloads, meeting links, phone numbers, emails, child data, payment data, or production exports. Store secrets in AWS Secrets Manager and encrypt sensitive records with KMS-backed envelope encryption. Rotate a credential immediately if exposure is suspected.

Public provider webhooks require raw-body signature and replay-window verification. Internal calls require short-lived JWT or HMAC with key IDs, timestamps, audience checks, and replay protection. See `docs/security/` for the threat model and incident process.

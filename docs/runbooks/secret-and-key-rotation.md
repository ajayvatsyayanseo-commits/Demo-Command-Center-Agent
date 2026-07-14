# Secret and key rotation

Use for scheduled rotation or suspected compromise of internal HMAC, field encryption, database,
Redis, Meta, Cashfree, Google, SES/AWS, OpenAI, or onboarding compatibility credentials.

## Scheduled HMAC rotation

1. Create the new secret in the approved secret store and assign a new key ID, one source identity,
   a least-privilege scope allowlist, and a validity window.
2. Deploy verifiers accepting current and new server-side key grants; do not put secret values in
   Terraform variables, workflow output, logs, or tickets. Never broaden authority from the signed
   source/scope headers alone.
3. Switch the signer to the new key, observe authentication/replay telemetry, then retire the old key
   after the maximum overlap/retry window.
4. Test wrong/expired key, audience, source, scope, timestamp, nonce replay, and request-body binding.

## Provider or data-key rotation

- Pause the affected capability when overlap is unsupported. Update the provider and Secrets Manager
  reference, restart tasks through the deployment process, canary, then revoke the prior credential.
- For field encryption, retain key references and execute a reviewed, restartable re-encryption plan;
  never delete an old key while retained ciphertext or backups require it.
- Database credentials rotate through Aurora/Secrets Manager and RDS Proxy; verify old sessions and
  task access expire as designed.

## Emergency rotation

Revoke first when continued use is unsafe, block the affected route/effect, preserve access evidence,
rotate, reconcile missed/uncertain work, and review blast radius. A security/privacy incident runs in
parallel when data exposure is possible.

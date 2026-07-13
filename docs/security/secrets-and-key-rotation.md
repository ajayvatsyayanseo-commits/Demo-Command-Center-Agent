# Secrets and key rotation

Secrets live in AWS Secrets Manager, encrypted with environment KMS keys, and are injected/retrieved by least-privilege task roles. GitHub uses OIDC and role assumption; workflows contain no AWS keys, account IDs, ARNs, or provider credentials. Secret values never appear in Terraform state variables when a runtime ARN/reference suffices.

Key-bearing contracts include a key ID and support an overlap window: publish new key, deploy verifiers accepting old/new, switch signer, verify telemetry, retire old, and record audit. Emergency rotation revokes first, pauses affected capability, deploys new reference, reconciles missed work, and reviews access/provider logs.

Rotate internal signing secrets, Cashfree/Meta credentials, Google OAuth/delegation material, database credentials, encryption data-key policy, and OpenAI keys under owner-specific schedules and after personnel/scope/incidents. Workload identity is preferred to static service-account keys. Applications cache secrets only briefly and never log secret-shaped values; doctor reports presence, not content.

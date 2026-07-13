# Threat model

Assets: demo/identity/consent state, restricted messages and meeting links, tutor contact, payment bindings, provider credentials, signing keys, lifecycle authority, regional analytics, and audit evidence.

| Threat | Control |
|---|---|
| Forged/replayed Meta or Cashfree callback | Raw-body HMAC, timestamp window, provider event uniqueness, WAF/rate limit |
| Forged internal handoff | Private networking where possible, short JWT/HMAC, audience/key ID/time/nonce, replay store |
| Duplicate booking/payment/send | PostgreSQL constraints, inbox/outbox, operation idempotency, reconciliation |
| IDOR/region escalation | Laravel-issued scoped claims, tenant+region repository predicates, audited override |
| Prompt/tool injection | Redaction, strict schema, allowlisted tasks/tools, deterministic policy gate, no direct tool invocation |
| SSRF/arbitrary URL | Provider-specific fixed base URLs, no model/user URL selection, DNS/network egress controls |
| SQL injection | Typed repositories/bind parameters; no LLM SQL or arbitrary filters |
| Secret/PII leakage | Secrets Manager/KMS, structured allowlist logs, masking tests, encrypted fields, analytics denylist |
| Child/guardian harm | Data minimization, guardian relationship/consent, safeguarding handoff, restricted access |
| Abuse/spam/cost exhaustion | IP/phone/user/tenant/endpoint/provider limits, budgets, circuit breakers, kill switches |
| Supply-chain/image compromise | Locked dependencies, SAST/audit/SBOM/signing/scans, non-root minimal image, OIDC |
| Audit tampering | Append-only access, hash chain, restricted roles, archive/object lock when approved |

Highest-risk flows are public provider callbacks, payment activation, scheduling conflicts, admin regional exports, content generation, and paid onboarding handoff. Each has fail-closed behavior and a human escalation path.

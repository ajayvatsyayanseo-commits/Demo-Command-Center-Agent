# Trust boundaries

1. **Internet to WAF/ALB/API:** only declared provider callbacks are public; strict TLS/content type/size/rate limits. Admin browser access is mediated by Laravel and short-lived scoped service tokens.
2. **Lead/Onboarding/Website to API:** never trust network location alone. Verify key ID/signature/JWT audience/issuer/time/replay and tenant/region claims.
3. **Application to providers:** fixed HTTPS endpoints, least scopes, timeouts, circuit breakers, sanitized telemetry, idempotent operation records.
4. **Application to PostgreSQL/Redis/SQS:** private subnets/security groups, TLS/auth, task-role/secret scope. PostgreSQL owns truth; Redis is disposable.
5. **Operational to analytics:** explicit allowlist and pseudonymization before S3; analysts cannot decrypt operational PII.
6. **LLM boundary:** only minimized/redacted content; output is untrusted data parsed/validated before any application decision.
7. **Environment boundary:** separate accounts or strongly isolated VPC/data/secrets/state/roles. Production data cannot enter dev tests.

Security groups allow only required source-to-destination ports. Task execution role pulls image/logs/secrets bootstrap; task role has operation-specific AWS permissions. Humans use SSO roles, no shared keys, with break-glass audit and expiry.

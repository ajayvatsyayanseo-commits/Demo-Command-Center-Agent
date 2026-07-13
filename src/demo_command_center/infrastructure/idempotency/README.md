# Idempotency

Reserve `(tenant, scope, key)` with canonical request hash; return stored result for identical retries and reject key reuse with different content.

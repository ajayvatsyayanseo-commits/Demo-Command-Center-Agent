# Cashfree integration

Demo-conversion order creation uses the official REST boundary through `httpx`: explicit API version, environment allowlist, TLS, connect/read/total timeouts, no arbitrary URL, stable application order ID, and persisted request/response metadata with sensitive fields removed.

The order binds purpose, tenant, demo, website user, plan/version, approved offer/discount decision, amount minor, currency, expiry, and idempotency key. A payment link/order is shared only after successful provider creation is stored. Retry first reconciles by application order ID.

Webhook processing uses the untouched raw body, Cashfree signature/timestamp headers, configured secret, replay window, event/order uniqueness, content/size limits, and durable inbox before acknowledgement. The service compares every bound field and obtains authenticated order status when event semantics are insufficient. Only a verified paid status plus successful idempotent website activation transitions to `PAID`.

Browser return is informational. A user message saying paid is informational. Unknown orders, amount/currency/user/plan mismatch, late payment, conflicting terminal status, duplicate activation attempt, refund, and dispute enter `PAYMENT_REVIEW`. Reconciliation CLI reports configuration/connection/sandbox/live validation separately and never modifies without explicit command/approval.

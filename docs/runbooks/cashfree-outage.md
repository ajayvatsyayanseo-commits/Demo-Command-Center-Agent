# Cashfree outage

Use for Cashfree API timeout/429/5xx, webhook gaps, invalid-signature spikes, or an elevated payment
reconciliation backlog.

## Contain

1. Disable new payment order/link creation with the approved payment kill switch. Keep the signed
   webhook boundary available unless compromise is suspected.
2. Continue durable acceptance of valid provider events; never acknowledge invalid signatures as
   business success.
3. Leave uncertain orders in pending/reconciliation or `PAYMENT_REVIEW`. Do not use a browser
   return, frontend callback, WhatsApp claim, or operator assertion as payment evidence.
4. If credential compromise is suspected, block the callback, preserve raw-body hashes/encrypted
   evidence, and start emergency rotation.

## Reconcile and recover

- Bind the local purpose, demo, user/customer, plan/version, offer, amount minor, currency,
  environment, provider order, and expiry before considering a terminal result.
- Query authenticated server status for uncertain orders. Treat unknown/mismatched/refunded/
  disputed results as review, not paid.
- Verify the website activation ledger and local paid-transition uniqueness independently.
- Canary one sandbox order, signed webhook, duplicate webhook, provider status lookup, and
  idempotent website activation before production resume.
- Gradually reopen new orders; continue reconciliation until the backlog is zero or individually
  assigned.

Finance approval is required for refunds, disputes, reversals, and manual customer remedies. Legal
or consumer-communications review may be required; code does not establish those obligations.


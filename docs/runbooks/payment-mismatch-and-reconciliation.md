# Payment mismatch and reconciliation

Use for amount/currency/customer/plan/environment/purpose mismatch, unknown or conflicting order,
duplicate activation, refund/dispute, or reconciliation backlog.

## Contain

1. Pause new payment links and website activations when the problem may be systemic. Continue
   signature-verified webhook capture so evidence is not lost.
2. Move the affected operation to review/reconciliation; never mark it paid manually or from a
   browser return, WhatsApp claim, or unsigned payload.
3. Preserve encrypted provider payload, raw-body hash, signature/timestamp result, local order
   binding, transition/outbox rows, and website activation ledger reference.

## Reconcile one order

1. Verify the local order purpose, demo, tenant, user/customer, plan/version, approved offer,
   amount minor, currency, environment, expiry, and provider order reference.
2. Fetch authenticated Cashfree server status and payment evidence. Treat any unresolved field or
   non-approved terminal status as review.
3. Check whether the local paid-transition unique record exists and whether the website activation
   ledger applied the exact same binding. Retry activation only with the original stable key.
4. Record one of: pending/retry, verified paid and activation applied, rejected evidence, expired,
   failed, refund/dispute review, or human/finance escalation.

Review a read-only provider/local/website comparison before invoking the scheduled reconciliation
command. The command is feature-gated, operates in bounded batches, records provider snapshot hashes
and audit evidence, and deliberately sends an order-level `PAID` result to review because it lacks a
provider payment ID; it does not bypass signed payment evidence. Canary and compare all three systems
after recovery. Refunds, reversals, disputes, and customer remedies require finance policy and may
require legal review.

# Disaster recovery

Use for regional AWS loss, unrecoverable primary data-service failure, broad credential compromise,
or prolonged loss of the service control plane. Environment RTO/RPO and disaster authority must be
approved before production; this repository phase did not execute a restore drill.

## Declare and stabilize

1. Declare the disaster, incident commander, recovery region/account, target RTO/RPO, and data
   recovery point. Freeze deployments and pause outbound, new bookings, and new payments.
2. Preserve DNS, image digest, Terraform state/version, database backup/PITR point, queue positions,
   secrets/key references, and provider callback ownership evidence.
3. Keep exactly one Meta owner and one Cashfree callback owner. Do not activate a recovery callback
   while the primary can still process it without explicit mutual exclusion.

## Restore order

1. Establish trusted identity/KMS/secrets and reviewed Terraform state.
2. Restore private network, Aurora/RDS Proxy, Redis, queues/DLQs, buckets, ECS API/workers, and
   observability. Treat Redis as disposable acceleration, not restored truth.
3. Apply compatible migrations to the recovered Aurora copy and validate constraints/inbox/outbox.
4. Deploy the known-good immutable image with all external-effect features off.
5. Restore verified provider/gateway configuration, then switch DNS/callbacks under explicit change
   control.

## Reconcile and reopen

Reconcile events between the recovery point and provider/source systems, including Lead Intake,
Calendar, Cashfree, Laravel activation ledger, SES, and Onboarding. Canary health, signed handoff,
booking, notification, payment evidence, and idempotency. Reopen one capability at a time and monitor
queue age, duplicates, and cross-system disagreement. Run a post-incident/legal/privacy review when
data loss, disclosure, or customer impact is possible.

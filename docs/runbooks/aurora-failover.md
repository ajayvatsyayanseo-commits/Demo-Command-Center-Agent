# Aurora failover and PostgreSQL unavailability

Use for connection failure, failover, RDS Proxy saturation, lock/CPU/storage pressure, corruption
concern, or an unhealthy writer.

## Contain

1. Readiness must fail and workers must stop taking new stateful work. SQS retains work; do not
   switch to an in-memory database or local adapter.
2. Pause new bookings/payments/outbound effects when their durable transaction cannot be committed.
3. Preserve provider retry behavior and avoid restart storms. Shed analytics/evaluation and other
   noncritical load first.
4. Record cluster/proxy event times, application image digest, migration revision, and sanitized
   pool/lock metrics.

## Recover

- Use AWS-managed failover for an available replica and verify the RDS Proxy target becomes healthy.
- For corruption/data-loss concern, stop writers and follow the approved snapshot/PITR decision;
  never restore over the only copy.
- Validate TLS, credentials, writer identity, migration head, representative constraints, and
  application readiness before consumers resume.
- Reconcile inbox/outbox leases, uncertain provider operations, slot holds, and payment events.
- Resume one worker/API slice, monitor lock/connection/queue age, then scale gradually.

PITR/failover drills, RTO/RPO, backup retention, and restore ownership require environment approval
and have not been exercised by this repository work.


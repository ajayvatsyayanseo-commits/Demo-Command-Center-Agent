# Deployment rollback

Use for failed health/smoke, migration incompatibility, correctness/security regression, or an
alarm-triggered release stop.

## Decide and contain

1. Stop promotion and activate the narrow safety flags for outbound, new bookings, payments,
   discounts, OpenAI, or the affected provider.
2. Record current/prior immutable image digests, task definitions, migration revision, configuration
   version, alarm window, and incident/change reference.
3. Determine whether the prior application digest is compatible with the current schema and event
   versions. Never automatically downgrade or destructively roll back the database.

## Roll back

1. Use the protected rollback workflow with the known-good digest and incident reference.
2. Wait for API and worker ECS stability; verify live, ready, queue/DB dependency state, and a safe
   synthetic internal handoff.
3. Reconcile external effects accepted during the bad release: outbound messages, Calendar events,
   Cashfree orders/events, website activations, and onboarding handoffs.
4. Keep risky capabilities off until the reconciliation and monitored canary are complete.

If schema compatibility is not established, deploy a forward-compatible fix rather than forcing a
downgrade. Archive workflow output and post-rollback evidence; rollback success is not proof that a
remote effect was undone.


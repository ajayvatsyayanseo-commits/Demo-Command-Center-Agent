# SQS backlog and DLQ

Use for oldest-message/depth alarms, poison messages, repeated visibility expiry, or any non-empty
DLQ.

## Backlog triage

1. Identify queue, oldest age, arrival/service rates, receive count, worker health, downstream
   provider/database state, and current deployment digest.
2. Scale workers only within approved DB/provider/cost limits. Pause noncritical producers when
   downstream recovery would otherwise worsen.
3. Verify long polling, visibility timeout/extension, bounded concurrency, and deletion only after
   durable inbox acceptance.
4. Do not delete or repeatedly receive messages merely to clear a metric.

## DLQ inspection and redrive

1. Sample using redacted metadata and classify schema/auth/policy poison, deterministic code defect,
   transient dependency failure, or already-applied side effect.
2. Fix or quarantine deterministic poison before redrive. Reconcile provider state for any message
   that may have crossed a side-effect boundary.
3. Record source/DLQ ARNs, count, time range, event versions, reason, approver, and a bounded batch
   size. Use the guarded repository redrive command only after reviewing its `--help` and required
   confirmation input; never bulk move an unclassified DLQ.
4. Canary a small batch, verify inbox/idempotency/outbox results, then increase gradually. Stop on
   repeat failures or duplicate-effect signals.

Close only when backlog age is within the approved objective, DLQ is empty or every item is assigned,
and business-effect reconciliation is recorded.


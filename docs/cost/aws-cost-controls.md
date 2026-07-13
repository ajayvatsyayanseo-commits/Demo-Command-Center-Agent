# AWS cost controls

- Separate tagged budgets/alerts by environment, service, owner, capability, and cost center.
- Autoscale API on request/latency and workers on queue age/depth with explicit min/max; evaluation workers default to zero/on-demand.
- Use SQS long polling/batching where ordering and failure isolation allow it.
- EventBridge one-shot schedules replace always-running in-process schedulers.
- Right-size Aurora/Redis from load evidence; use RDS Proxy connection budgets and nonproduction schedules where safe.
- Apply S3 lifecycle/Intelligent-Tiering rules to artifacts/analytics/backups under retention policy; constrain Athena workgroups scan bytes.
- Set CloudWatch log retention/metric cardinality limits and sampling without losing security/payment traces.
- Prefer VPC endpoints only after comparing NAT/endpoint/security needs; monitor egress.
- Store one immutable image and promote digest; clean unreferenced ECR images under policy.
- Kill switches stop OpenAI, new bookings, reminders, automatic payment links, and noncritical analytics separately.

Budget alarms never silently drop already-accepted critical work. They pause new expensive/noncritical operations and open an owner ticket.

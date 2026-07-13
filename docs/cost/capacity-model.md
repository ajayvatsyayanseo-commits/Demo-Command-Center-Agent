# Capacity model

These are planning variables, not production claims. Values must be set from measured business forecasts before Terraform sizing.

| Variable | Symbol / derivation |
|---|---|
| Registered identities | `R` (design target at least 1,000,000 records; not concurrency) |
| Monthly/daily active identities | `MAU`, `DAU` |
| Concurrent conversations | `C = peak_active_sessions`, measured separately from `R` |
| Inbound steady/burst messages/s | `M`, `Mb`; SQS/API sized for `Mb` with recovery target |
| Demos/day | `D`; slots/holds/confirmations derived by funnel rates |
| Reminders/day | `D * reminders_per_demo + reschedule adjustments` |
| Calendar calls/day | free/busy candidates + create/update/cancel + reconciliation |
| Cashfree calls/day | conversion attempts + status reconciliation, not all demos |
| OpenAI calls/day | objection/summarization/drafting eligibility and fallback rate |
| DB writes/day | events + transitions + comms/provider attempts + audit |
| Queue depth/age | arrival/service rate per queue; autoscale on oldest age and depth |
| Storage growth | row bytes * daily facts * retention + index/backup factor |
| Analytics volume | sanitized facts only; partition/scan bytes per query |

Unit cost model sums ECS vCPU/memory hours, Aurora ACU/storage/I/O/backups, RDS Proxy, Redis nodes, SQS requests, EventBridge schedules, ALB/WAF/egress, S3/Glue/Athena scans, SES messages, observability ingestion/retention, Google/Meta/Cashfree pricing where applicable, and OpenAI input/output tokens. Track cost per scheduled demo, completed demo, and verified paid conversion.

Load tests model typical, burst/retry storm, provider slowdown, duplicate webhook, and worker recovery. Capacity approval records assumptions, headroom, queue recovery time, DB connection budget through RDS Proxy, and budget alarms. Registered identities alone do not size concurrent compute.

# ADR-011: AWS runtime

- Status: Accepted
- Date: 2026-07-13

## Context

The workload has HTTP, queue, scheduled, and occasional evaluation profiles and requires private managed persistence with horizontal scaling.

## Decision

Run one immutable image on ECS Fargate as API/worker/optional evaluation tasks in private multi-AZ subnets. Use ALB/WAF, Aurora PostgreSQL with RDS Proxy, ElastiCache Redis, SQS+DLQ, EventBridge Scheduler, S3, SES, Secrets Manager, KMS, CloudWatch/OTel, Glue/Athena, ECR, and GitHub OIDC. Use VPC endpoints where cost/security justify them.

## Consequences

There are no long-lived CI AWS keys or public database/cache endpoints. Queue age/depth drives worker scaling. Environment isolation and cost tags are mandatory. Exact VPC, quotas, Route 53, certificates, SES status, and account details remain deployment inputs.

## 2026-07-14 Lambda addendum

The repository also exposes an API-only AWS Lambda handler at
`demo_command_center.lambda_handler.handler` using Mangum for API Gateway v2 / Lambda Function URL
compatibility. This is a deployment convenience for the FastAPI HTTP surface; it does not replace
the accepted ECS worker/runtime model for SQS consumers, migrations, reconciliation, reminders,
model evaluation, or long-running operational tasks. Promoting Lambda to the primary production
runtime requires a new ADR plus equivalent VPC, RDS Proxy, Redis, SQS, observability, timeout,
concurrency, cold-start, and rollback evidence.

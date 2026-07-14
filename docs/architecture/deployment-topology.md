# Deployment topology

```mermaid
flowchart TB
    Internet --> R53[Route 53 / ACM]
    R53 --> WAF[AWS WAF]
    WAF --> ALB[Public ALB]
    subgraph PrivateApp[Private application subnets, 2+ AZ]
      API[ECS Fargate API]
      Worker[ECS Fargate workers]
      Eval[Optional evaluation task]
      Proxy[RDS Proxy]
      Redis[ElastiCache Redis]
    end
    ALB --> API
    API --> Proxy
    Worker --> Proxy
    Proxy --> Aurora[(Aurora PostgreSQL Multi-AZ)]
    API --> Redis
    Worker --> Redis
    API --> SQS[SQS queues + per-queue DLQs]
    SQS --> Worker
    EB[EventBridge Scheduler] --> SQS
    API --> VPCE[VPC endpoints / NAT egress]
    Worker --> VPCE
    VPCE --> Providers[Google / Cashfree / OpenAI / SES]
    Worker --> S3[S3 encrypted artifacts/analytics]
    CW[CloudWatch + OTel] --- API
    CW --- Worker
```

Database/cache have no public route. Tasks use least-privilege roles and Secrets Manager/KMS. Dev, staging, and prod have separate state, networks/data, secrets, queues, and GitHub Environment approvals. Images are built once, identified by digest, scanned, promoted, and rolled back without rebuilding.

An optional API-only Lambda entrypoint exists for AWS environments that prefer API Gateway v2 or a
Lambda Function URL for the HTTP surface. The lifecycle worker, outbox publisher, scheduled jobs,
migrations, reconciliation, and evaluation tasks remain ECS/SQS process types under the accepted
runtime ADR unless a future ADR explicitly changes them.
